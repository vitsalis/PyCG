use num_bigint::BigInt;
use pycg_solver::{NodeId, ObjId};
use pycg_stubs::Type;
use rustc_hash::{FxHashMap, FxHashSet};

use crate::engine::objects::{Kind, Literal, Object};
use crate::engine::outside_calls::{BoundId, Known};
use crate::engine::outside_types::TypeContext;
use crate::engine::rules::{Rule, RuleId};
use crate::engine::semantics::CallId;
use crate::engine::symbols::Sym;
use crate::engine::{Graph, State};
use crate::models::{DECORATING_CLOSURES, opened_class};

const FUNCTION_KINDS: &[Kind] = &[Kind::Function];
const DEFAULT_MODE: &str = "r";
const TYPE: &str = "builtins.type";
const NONE_TYPE: &str = "types.NoneType";
const CALL: &str = "__call__";
const NUMERIC_PROMOTIONS: &[(&str, &[&str])] = &[
    ("builtins.float", &["builtins.int"]),
    ("builtins.complex", &["builtins.int", "builtins.float"]),
];

#[derive(Clone, Debug)]
pub(crate) enum OutsideResultRule {
    MethodFunction {
        receiver: NodeId,
        dst: NodeId,
    },
    BoundTo {
        function: ObjId,
        dst: NodeId,
    },
    NewInstance {
        call: CallId,
        dst: NodeId,
    },
    MadeInstance {
        call: CallId,
        dst: NodeId,
    },
    OpenMode {
        call: CallId,
        buffering: Option<NodeId>,
        results: Box<[(Type, TypeContext)]>,
        dst: NodeId,
    },
    OpenBuffering {
        mode: Box<[u32]>,
        dst: NodeId,
    },
    Overload {
        bound: BoundId,
        annotation: Type,
        result: Box<(Type, TypeContext)>,
        dst: NodeId,
    },
}

impl OutsideResultRule {
    pub(crate) fn kinds(&self) -> Option<&'static [Kind]> {
        match self {
            OutsideResultRule::MethodFunction { .. } => Some(FUNCTION_KINDS),
            _ => None,
        }
    }

    pub(crate) fn captured(&self) -> Vec<ObjId> {
        match *self {
            OutsideResultRule::BoundTo { function, .. } => vec![function],
            _ => Vec::new(),
        }
    }

    pub(crate) fn results(&self) -> Vec<NodeId> {
        match *self {
            OutsideResultRule::MethodFunction { dst, .. }
            | OutsideResultRule::BoundTo { dst, .. }
            | OutsideResultRule::NewInstance { dst, .. }
            | OutsideResultRule::MadeInstance { dst, .. }
            | OutsideResultRule::OpenMode { dst, .. }
            | OutsideResultRule::OpenBuffering { dst, .. }
            | OutsideResultRule::Overload { dst, .. } => vec![dst],
        }
    }
}

#[derive(Default)]
pub(crate) struct OutsideResults {
    closures: FxHashMap<(Sym, Type), ObjId>,
    deciding_arguments: Vec<NodeId>,
    deciding_copies: FxHashMap<NodeId, NodeId>,
    completed_deciding_arguments: usize,
    unknown_modes: FxHashSet<CallId>,
    open_modes: FxHashSet<(CallId, Box<[u32]>)>,
    selected_overloads: FxHashSet<(BoundId, Option<ObjId>)>,
}

impl State {
    fn result_rule(&mut self, rule: OutsideResultRule) -> RuleId {
        self.rule(Rule::OutsideResult(Box::new(rule)))
    }

    pub(super) fn closure(&mut self, graph: &mut Graph, name: &str, result: &Type) -> ObjId {
        let name = self.symbols.intern(name);
        let key = (name, result.clone());
        if let Some(&closure) = self.outside_results.closures.get(&key) {
            return closure;
        }
        let object = Object::Closure {
            name,
            result: Box::new(result.clone()),
        };
        let closure = self.new_object(graph, object);
        self.outside_results.closures.insert(key, closure);
        closure
    }

    pub(super) fn call_closure(&mut self, graph: &mut Graph, closure: ObjId, call: CallId) {
        let Object::Closure { name, result } = self.objects.get(closure) else {
            panic!("a closure")
        };
        let (name, result) = (*name, (**result).clone());
        self.add_external_call_edge(call, name, Known::Stub);
        let details = &self.calls[call.index()];
        let Some(dst) = details.dst else {
            return;
        };
        let context = TypeContext::of_call(call, details.origin);
        self.add_type(graph, &result, dst, &context, &[]);
        let details = &self.calls[call.index()];
        let applied = details.applies && DECORATING_CLOSURES.contains(&self.symbols.text(name));
        if (details.decorator || applied)
            && let Some(&Some(decorated)) = details.args.last()
        {
            self.add_edge(graph, decorated, dst);
        }
    }

    pub(super) fn make_method(&mut self, graph: &mut Graph, call: CallId) {
        let details = &self.calls[call.index()];
        let dst = details.dst.expect("a made method has a result");
        let &[Some(function), Some(receiver)] = details.args.as_slice() else {
            return;
        };
        if !details.star.is_empty() || !details.keywords.is_empty() {
            return;
        }
        let rule = self.result_rule(OutsideResultRule::MethodFunction { receiver, dst });
        self.attach(graph, function, rule);
    }

    pub(super) fn new_instance_of(&mut self, graph: &mut Graph, call: CallId) {
        let details = &self.calls[call.index()];
        let (Some(dst), Some(&Some(class))) = (details.dst, details.args.first()) else {
            return;
        };
        let rule = self.result_rule(OutsideResultRule::NewInstance { call, dst });
        self.attach(graph, class, rule);
    }

    pub(super) fn open_file(
        &mut self,
        graph: &mut Graph,
        call: CallId,
        bound: BoundId,
        results: Vec<(Type, TypeContext)>,
    ) {
        let buffering = if self.bound_given(bound, "buffering") {
            let node = self.bound_parameter(graph, bound, "buffering");
            Some(self.deciding_argument(graph, node))
        } else {
            None
        };
        if self.bound_given(bound, "mode") {
            let node = self.bound_parameter(graph, bound, "mode");
            let mode = self.deciding_argument(graph, node);
            let dst = self.calls[call.index()].dst.expect("an opened file");
            let rule = self.result_rule(OutsideResultRule::OpenMode {
                call,
                buffering,
                results: results.into_boxed_slice(),
                dst,
            });
            self.attach(graph, mode, rule);
        } else {
            let mode: Box<[u32]> = DEFAULT_MODE.chars().map(u32::from).collect();
            self.opened(graph, mode, call, buffering);
        }
    }

    pub(super) fn deciding_argument(&mut self, graph: &mut Graph, node: NodeId) -> NodeId {
        if let Some(&copy) = self.outside_results.deciding_copies.get(&node) {
            return copy;
        }
        let copy = self.node(graph, None);
        self.add_edge(graph, node, copy);
        self.outside_results.deciding_arguments.push(copy);
        self.outside_results.deciding_copies.insert(node, copy);
        copy
    }

    fn opened(
        &mut self,
        graph: &mut Graph,
        mode: Box<[u32]>,
        call: CallId,
        buffering: Option<NodeId>,
    ) {
        let dst = self.calls[call.index()].dst.expect("an opened file");
        let Some(buffering) = buffering else {
            self.add_opened(graph, &mode, &[false], dst);
            return;
        };
        if self.outside_results.open_modes.insert((call, mode.clone())) {
            let rule = self.result_rule(OutsideResultRule::OpenBuffering { mode, dst });
            self.attach(graph, buffering, rule);
        }
    }

    fn add_opened(&mut self, graph: &mut Graph, mode: &[u32], unbuffered: &[bool], dst: NodeId) {
        let mode: Option<String> = mode.iter().map(|&point| char::from_u32(point)).collect();
        let Some(mode) = mode else {
            return;
        };
        for &each in unbuffered {
            if let Some(class) = opened_class(&mode, each) {
                let typed = self.typed(graph, class);
                self.add_object(graph, dst, typed);
            }
        }
    }

    pub(super) fn select_overload(
        &mut self,
        graph: &mut Graph,
        argument: NodeId,
        bound: BoundId,
        annotation: &Type,
        result: (Type, TypeContext),
        dst: NodeId,
    ) {
        let copy = self.deciding_argument(graph, argument);
        let rule = self.result_rule(OutsideResultRule::Overload {
            bound,
            annotation: annotation.clone(),
            result: Box::new(result),
            dst,
        });
        self.attach(graph, copy, rule);
    }

    pub(super) fn accepts(&mut self, object: ObjId, annotation: &Type) -> bool {
        let Some(class) = self.stub_class(object) else {
            return true;
        };
        let mut pending = vec![annotation];
        while let Some(current) = pending.pop() {
            let accepted = match current {
                Type::Union(arms) => {
                    pending.extend(arms.iter());
                    false
                }
                Type::Variable {
                    bound: Some(bound), ..
                } => {
                    pending.push(bound);
                    false
                }
                Type::Class(expected) => self.instance_of(&class, expected),
                Type::Generic(expected, arguments) => {
                    self.instance_of(&class, expected)
                        && self.constraint_agrees(object, expected, arguments)
                }
                Type::None => self.instance_of(&class, NONE_TYPE),
                Type::TypeOf(_) => self.instance_of(&class, TYPE),
                Type::Callable { .. } => !self.stubs.member(&class, CALL).is_empty(),
                Type::Unknown | Type::SelfType | Type::Ellipsis | Type::Variable { .. } => true,
            };
            if accepted {
                return true;
            }
        }
        false
    }

    fn constraint_agrees(&mut self, object: ObjId, expected: &str, arguments: &[Type]) -> bool {
        let &Object::Typed {
            class,
            constraint: Some(constraint),
            ..
        } = self.objects.get(object)
        else {
            return true;
        };
        if self.symbols.text(class) != expected {
            return true;
        }
        let Some(parameter) = self.constrained_parameter(expected) else {
            return true;
        };
        match arguments.get(parameter.position) {
            Some(Type::Class(declared)) => **declared == *self.symbols.text(constraint),
            _ => true,
        }
    }

    fn instance_of(&mut self, class: &str, expected: &str) -> bool {
        let mro = self.stubs.mro(class);
        if mro.iter().any(|owner| &**owner == expected) {
            return true;
        }
        if let Some(&(_, promoted)) = NUMERIC_PROMOTIONS.iter().find(|&&(to, _)| to == expected)
            && mro.iter().any(|owner| promoted.contains(&&**owner))
        {
            return true;
        }
        let members = self.protocol_methods(expected);
        !members.is_empty()
            && members
                .iter()
                .all(|name| !self.stubs.member(class, name).is_empty())
    }

    pub(super) fn complete_deciding_arguments(&mut self, graph: &mut Graph) -> bool {
        let start = self.outside_results.completed_deciding_arguments;
        let pending = self.outside_results.deciding_arguments[start..].to_vec();
        self.outside_results.completed_deciding_arguments =
            self.outside_results.deciding_arguments.len();
        let empty: Vec<NodeId> = pending
            .into_iter()
            .filter(|&node| self.objects_of(graph, node).is_empty())
            .collect();
        let unknown = self.unknown_external;
        for &node in &empty {
            self.add_object(graph, node, unknown);
        }
        !empty.is_empty()
    }

    pub(super) fn outside_result_apply(
        &mut self,
        graph: &mut Graph,
        rule: &OutsideResultRule,
        object: ObjId,
    ) {
        match *rule {
            OutsideResultRule::MethodFunction { receiver, dst } => {
                let rule = self.result_rule(OutsideResultRule::BoundTo {
                    function: object,
                    dst,
                });
                self.attach(graph, receiver, rule);
            }
            OutsideResultRule::BoundTo { function, dst } => {
                let method = self.bound_method(graph, object, function);
                self.add_object(graph, dst, method);
            }
            OutsideResultRule::NewInstance { call, dst } => {
                self.new_instance(graph, object, call, dst)
            }
            OutsideResultRule::MadeInstance { call, dst } => {
                let instance = self.instance(graph, object, call);
                self.add_object(graph, dst, instance);
            }
            OutsideResultRule::OpenMode {
                call,
                buffering,
                ref results,
                dst,
            } => {
                if let Object::Const {
                    value: Literal::Str(mode),
                    ..
                } = self.objects.get(object)
                {
                    let mode = mode.clone();
                    self.opened(graph, mode, call, buffering);
                } else if self.outside_results.unknown_modes.insert(call) {
                    for (reduced, context) in results {
                        self.add_type(graph, reduced, dst, context, &[]);
                    }
                }
            }
            OutsideResultRule::OpenBuffering { ref mode, dst } => {
                let unbuffered: &[bool] = match self.objects.get(object) {
                    Object::Const {
                        value: Literal::Int(value),
                        ..
                    } => &[*value == BigInt::from(0u8)],
                    _ => &[false, true],
                };
                let mode = mode.clone();
                self.add_opened(graph, &mode, unbuffered, dst);
            }
            OutsideResultRule::Overload {
                bound,
                ref annotation,
                ref result,
                dst,
            } => {
                let (reduced, context) = &**result;
                let key = (bound, context.receiver);
                if !self.outside_results.selected_overloads.contains(&key)
                    && self.accepts(object, annotation)
                {
                    self.outside_results.selected_overloads.insert(key);
                    self.add_type(graph, reduced, dst, context, &[]);
                }
            }
        }
    }

    fn new_instance(&mut self, graph: &mut Graph, object: ObjId, call: CallId, dst: NodeId) {
        match self.objects.get(object) {
            Object::Class(class) => {
                let (mros, instances, instantiable) =
                    (class.mros.clone(), class.instances, class.instantiable);
                if mros.iter().all(|mro| self.derives_from_type(mro)) {
                    self.add_edge(graph, instances, dst);
                } else {
                    let rule = self.result_rule(OutsideResultRule::MadeInstance { call, dst });
                    self.attach(graph, instantiable, rule);
                }
            }
            Object::External(_) => {
                for value in self.outside_instance_of(graph, object) {
                    self.add_object(graph, dst, value);
                }
            }
            _ => {}
        }
    }
}

impl OutsideResults {
    pub(crate) fn table_sizes(&self, sizes: &mut Vec<(&'static str, usize)>) {
        let OutsideResults {
            closures,
            deciding_arguments,
            deciding_copies: _,
            completed_deciding_arguments: _,
            unknown_modes: _,
            open_modes,
            selected_overloads,
        } = self;
        sizes.extend([
            ("outside results closures", closures.len()),
            (
                "outside results deciding_arguments",
                deciding_arguments.len(),
            ),
            ("outside results open_modes", open_modes.len()),
            (
                "outside results selected_overloads",
                selected_overloads.len(),
            ),
        ]);
    }
}
