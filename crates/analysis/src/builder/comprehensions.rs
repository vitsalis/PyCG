use pycg_solver::NodeId;
use pycg_syntax::tree::Node;
use ruff_python_ast::{Comprehension, Expr};

use crate::builder::ModuleBuilder;
use crate::builder::calls::Analysis;
use crate::builder::expressions::add_once;
use crate::builder::flow::UNKNOWN;

enum Element<'e> {
    One(&'e Expr),
    Mapping(&'e Expr),
    Item { key: &'e Expr, value: &'e Expr },
}

impl<'a, 's, A: Analysis> ModuleBuilder<'a, 's, A> {
    pub(crate) fn comprehension(&mut self, node: &Node<'_>) -> NodeId {
        let (kind, element, generators): (&str, Element<'_>, &[Comprehension]) = match node {
            Node::Expr(Expr::ListComp(e)) => ("list", Element::One(&e.elt), &e.generators),
            Node::Expr(Expr::SetComp(e)) => ("set", Element::One(&e.elt), &e.generators),
            Node::Expr(Expr::DictComp(e)) => match &e.key {
                Some(key) => (
                    "dict",
                    Element::Item {
                        key,
                        value: &e.value,
                    },
                    &e.generators,
                ),
                None => ("dict", Element::Mapping(&e.value), &e.generators),
            },
            Node::Expr(Expr::Generator(e)) => ("generator", Element::One(&e.elt), &e.generators),
            Node::GeneratorArgument(e, _) => ("generator", Element::One(&e.elt), &e.generators),
            _ => unreachable!("a comprehension is one of the four comprehension kinds"),
        };
        let scope = self.scopes.scope_of(node);
        let kind = if kind == "generator" && self.scopes.scope(scope).asynchronous {
            "async_generator"
        } else {
            kind
        };
        let site = self.site(node);
        let container = self.analysis.container(kind, &site, None);
        let first = &generators[0];
        let mut elements = self.elements_of(&first.iter, first.is_async);
        let function = self.function.clone();
        self.inside(scope, function, |builder| {
            for (index, generator) in generators.iter().enumerate() {
                if index > 0 {
                    elements = builder.elements_of(&generator.iter, generator.is_async);
                }
                builder.assign(&generator.target, elements, UNKNOWN, None);
                for condition in &generator.ifs {
                    builder.condition_at(&Node::Expr(condition));
                }
            }
            builder.comprehension_element(container, kind, element);
        });
        self.analysis.constant(container)
    }

    fn comprehension_element(
        &mut self,
        container: pycg_solver::ObjId,
        kind: &str,
        element: Element<'_>,
    ) {
        let caller = self.caller().to_owned();
        match element {
            Element::Mapping(mapping) => {
                if let Some(value) = self.expression(mapping) {
                    let site = self.site(&Node::Expr(mapping));
                    self.analysis
                        .add_dict_items(container, value, &caller, &site);
                    add_once(
                        &mut self.analysis.tables().iterated_expressions,
                        (caller.into(), site.into()),
                    );
                }
            }
            Element::Item { key, value } => {
                let key_node = self.expression(key);
                let value_node = self.expression(value);
                self.analysis.write_keyed(container, key_node, value_node);
                if let Some(key_node) = key_node {
                    let stored = self.analysis.keys(container);
                    let site = self.site(&Node::Expr(key));
                    self.analysis
                        .add_hash(key_node, &caller, &site, Some(stored));
                }
            }
            Element::One(Expr::Starred(starred)) if kind == "set" => {
                if let Some((hashed, kept)) = self.entering(&starred.value) {
                    for value in [hashed, kept] {
                        let unknown = self.analysis.unknown(container);
                        self.analysis.add_edge(value, unknown);
                    }
                    let stored = self.analysis.elements(container);
                    let site = self.site(&Node::Expr(&starred.value));
                    self.analysis.add_hash(hashed, &caller, &site, Some(stored));
                }
            }
            Element::One(element @ Expr::Starred(starred)) => {
                if let Some(iterable) = self.expression(&starred.value) {
                    let target = self.analysis.unknown(container);
                    let site = self.site(&Node::Expr(element));
                    self.analysis
                        .add_iteration(iterable, target, &caller, &site, false);
                }
            }
            Element::One(element) => {
                if let Some(value) = self.expression(element) {
                    let unknown = self.analysis.unknown(container);
                    self.analysis.add_edge(value, unknown);
                    if kind == "set" {
                        let stored = self.analysis.elements(container);
                        let site = self.site(&Node::Expr(element));
                        self.analysis.add_hash(value, &caller, &site, Some(stored));
                    }
                }
            }
        }
    }
}
