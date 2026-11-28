use std::cell::RefCell;
use std::collections::BTreeMap;
use std::rc::Rc;

const MODULES_MAX: usize = 5;
const DEFINITIONS_PER_MODULE_MAX: usize = 5;
const IMPORTS_PER_MODULE_MAX: usize = 3;
const STATEMENTS_PER_BLOCK_MAX: usize = 4;
const BLOCK_DEPTH_MAX: usize = 3;
const EXPRESSION_DEPTH_MAX: usize = 3;
const BASES_PER_CLASS_MAX: usize = 3;
const METHODS_PER_CLASS_MAX: usize = 5;
const ARGUMENTS_PER_CALL_MAX: usize = 3;
const ELEMENTS_PER_CONTAINER_MAX: usize = 3;
const PARAMETERS_PER_KIND_MAX: usize = 2;
const CASES_PER_MATCH_MAX: usize = 3;
const PATTERN_DEPTH_MAX: usize = 2;

const PACKAGE: &str = "pkg";
const HEADER: [&str; 3] = ["import asyncio", "import contextlib", "import functools"];
const METHOD_NAMES: [&str; 4] = ["run", "get", "put", "close"];
const ATTRIBUTE_NAMES: [&str; 3] = ["value", "data", "handler"];
const KEYWORD_NAMES: [&str; 4] = ["key", "value", "default", "handler"];
const CONTAINER_METHODS: [&str; 11] = [
    "append",
    "extend",
    "pop",
    "get",
    "items",
    "keys",
    "values",
    "setdefault",
    "update",
    "add",
    "copy",
];
const CONSTANTS: [&str; 8] = ["0", "1", "2.5", "'k'", "'run'", "b'x'", "None", "True"];
const BUILTIN_CLASSES: [&str; 6] = ["int", "str", "list", "dict", "tuple", "object"];
const EXCEPTIONS: [&str; 4] = ["Exception", "ValueError", "KeyError", "TypeError"];
const SPLITMIX_INCREMENT: u64 = 0x9E37_79B9_7F4A_7C15;
const SPLITMIX_FIRST_MULTIPLIER: u64 = 0xBF58_476D_1CE4_E5B9;
const SPLITMIX_SECOND_MULTIPLIER: u64 = 0x94D0_49BB_1331_11EB;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Kind {
    Module,
    Class,
    Plain,
    Generator,
    Async,
    AsyncGenerator,
}

const FUNCTION_KINDS: [Kind; 4] = [
    Kind::Plain,
    Kind::Generator,
    Kind::Async,
    Kind::AsyncGenerator,
];

impl Kind {
    fn function(self) -> bool {
        FUNCTION_KINDS.contains(&self)
    }

    fn asynchronous(self) -> bool {
        matches!(self, Kind::Async | Kind::AsyncGenerator)
    }

    fn yielding(self) -> bool {
        matches!(self, Kind::Generator | Kind::AsyncGenerator)
    }
}

#[derive(Clone, Copy)]
enum Definition {
    Function,
    Decorator,
    Factory,
    Class,
    Diamond,
    Value,
}

const DEFINITION_KINDS: [Definition; 8] = [
    Definition::Function,
    Definition::Function,
    Definition::Decorator,
    Definition::Factory,
    Definition::Class,
    Definition::Class,
    Definition::Diamond,
    Definition::Value,
];

#[derive(Clone, Copy, PartialEq, Eq)]
enum Method {
    Init,
    Plain,
    Property,
    Static,
    OfClass,
    Call,
    Getattr,
    Getitem,
    Iter,
    Context,
    Async,
}

const METHOD_KINDS: [Method; 12] = [
    Method::Init,
    Method::Plain,
    Method::Plain,
    Method::Property,
    Method::Static,
    Method::OfClass,
    Method::Call,
    Method::Getattr,
    Method::Getitem,
    Method::Iter,
    Method::Context,
    Method::Async,
];

struct Random(u64);

impl Random {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(SPLITMIX_INCREMENT);
        let mut mixed = self.0;
        mixed = (mixed ^ (mixed >> 30)).wrapping_mul(SPLITMIX_FIRST_MULTIPLIER);
        mixed = (mixed ^ (mixed >> 27)).wrapping_mul(SPLITMIX_SECOND_MULTIPLIER);
        mixed ^ (mixed >> 31)
    }

    fn below(&mut self, bound: usize) -> usize {
        assert!(bound > 0, "a choice among nothing");
        let bound = u64::try_from(bound).expect("a bound");
        usize::try_from(self.next() % bound).expect("an index")
    }

    fn between(&mut self, minimum: usize, maximum: usize) -> usize {
        assert!(minimum <= maximum);
        minimum + self.below(maximum - minimum + 1)
    }

    fn choice<T: Clone>(&mut self, items: &[T]) -> T {
        items[self.below(items.len())].clone()
    }

    fn sample<T: Clone>(&mut self, items: &[T], count: usize) -> Vec<T> {
        assert!(count <= items.len());
        let mut pool = items.to_vec();
        let mut chosen = Vec::with_capacity(count);
        for _ in 0..count {
            let index = self.below(pool.len());
            chosen.push(pool.swap_remove(index));
        }
        chosen
    }
}

#[derive(Clone, Default)]
struct Exports {
    functions: Vec<String>,
    classes: Vec<String>,
    values: Vec<String>,
    decorators: Vec<String>,
    factories: Vec<String>,
}

impl Exports {
    fn lists(&self) -> [&Vec<String>; 5] {
        [
            &self.functions,
            &self.classes,
            &self.values,
            &self.decorators,
            &self.factories,
        ]
    }

    fn from_lists(mut lists: impl FnMut(&Vec<String>) -> Vec<String>, from: &Exports) -> Exports {
        Exports {
            functions: lists(&from.functions),
            classes: lists(&from.classes),
            values: lists(&from.values),
            decorators: lists(&from.decorators),
            factories: lists(&from.factories),
        }
    }

    fn names(&self) -> Vec<String> {
        self.lists().into_iter().flatten().cloned().collect()
    }

    fn callables(&self) -> Vec<String> {
        [
            &self.functions,
            &self.classes,
            &self.decorators,
            &self.factories,
        ]
        .into_iter()
        .flatten()
        .cloned()
        .collect()
    }

    fn qualified(&self, prefix: &str) -> Exports {
        Exports::from_lists(
            |names| {
                names
                    .iter()
                    .map(|name| format!("{prefix}.{name}"))
                    .collect()
            },
            self,
        )
    }

    fn merge(&mut self, other: &Exports) {
        self.functions.extend(other.functions.iter().cloned());
        self.classes.extend(other.classes.iter().cloned());
        self.values.extend(other.values.iter().cloned());
        self.decorators.extend(other.decorators.iter().cloned());
        self.factories.extend(other.factories.iter().cloned());
    }
}

struct Module {
    name: String,
    package: bool,
    definitions: Vec<(Definition, Vec<String>)>,
    exports: Exports,
}

impl Module {
    fn new(name: String, package: bool) -> Module {
        Module {
            name,
            package,
            definitions: Vec::new(),
            exports: Exports::default(),
        }
    }

    fn path(&self) -> String {
        let parts: Vec<&str> = self.name.split('.').collect();
        if self.package {
            format!("{}/__init__.py", parts.join("/"))
        } else {
            format!("{}.py", parts.join("/"))
        }
    }

    fn parent(&self) -> Vec<String> {
        let parts: Vec<String> = self.name.split('.').map(str::to_owned).collect();
        if self.package {
            parts
        } else {
            parts[..parts.len() - 1].to_vec()
        }
    }
}

#[derive(Default)]
struct Scope {
    variables: Vec<String>,
    globals: Vec<String>,
}

#[derive(Clone)]
struct Context {
    refs: Rc<Exports>,
    scope: Rc<RefCell<Scope>>,
    module_values: Rc<Vec<String>>,
    outer: Vec<String>,
    enclosing: Vec<String>,
    kind: Kind,
    looping: bool,
    owner: Option<String>,
    depth: usize,
    cleanup: bool,
}

impl Context {
    fn new(refs: Rc<Exports>, scope: Scope, module_values: Rc<Vec<String>>) -> Context {
        Context {
            refs,
            scope: Rc::new(RefCell::new(scope)),
            module_values,
            outer: Vec::new(),
            enclosing: Vec::new(),
            kind: Kind::Module,
            looping: false,
            owner: None,
            depth: 0,
            cleanup: false,
        }
    }

    fn visible(&self) -> Vec<String> {
        let scope = self.scope.borrow();
        let mut names = self.refs.names();
        names.extend(self.outer.iter().cloned());
        names.extend(scope.variables.iter().cloned());
        names.extend(scope.globals.iter().cloned());
        names
    }

    fn assigned(&self) -> Vec<String> {
        let scope = self.scope.borrow();
        let mut names = scope.variables.clone();
        names.extend(scope.globals.iter().cloned());
        names
    }

    fn add(&self, names: &[String]) {
        self.scope
            .borrow_mut()
            .variables
            .extend(names.iter().cloned());
    }
}

#[derive(Clone, Copy)]
enum Statement {
    Assignment,
    Unpacking,
    Expression,
    Reflection,
    Augmented,
    Annotated,
    Raise,
    Return,
    Yield,
    Jump,
    If,
    For,
    While,
    Try,
    With,
    Match,
    NestedFunction,
    NestedClass,
}

#[derive(Clone, Copy)]
enum Expression {
    Atom,
    Call,
    MethodCall,
    Attribute,
    Subscript,
    Container,
    Comprehension,
    Lambda,
    Reflection,
    ClassTest,
    Conditional,
    Builtin,
    Operation,
    Await,
    SuperCall,
}

struct Generator {
    random: Random,
    counter: usize,
    lines: Vec<String>,
    indent: usize,
}

pub fn program(seed: u64) -> BTreeMap<String, String> {
    let mut generator = Generator {
        random: Random(seed),
        counter: 0,
        lines: Vec::new(),
        indent: 0,
    };
    generator.program()
}

impl Generator {
    fn chance(&mut self) -> bool {
        self.random.below(2) == 0
    }

    fn count(&mut self, maximum: usize, minimum: usize) -> usize {
        self.random.between(minimum, maximum)
    }

    fn fresh(&mut self, prefix: &str) -> String {
        self.counter += 1;
        format!("{prefix}{}", self.counter)
    }

    fn emit(&mut self, line: &str) {
        self.lines
            .push(format!("{}{line}", "    ".repeat(self.indent)));
    }

    fn program(&mut self) -> BTreeMap<String, String> {
        let mut modules = self.modules();
        for module in &mut modules {
            self.plan(module);
        }
        let mut files = BTreeMap::new();
        for index in 0..modules.len() {
            let source = self.module(index, &modules);
            files.insert(modules[index].path(), source);
        }
        files
    }

    fn modules(&mut self) -> Vec<Module> {
        let mut modules = vec![Module::new("main".to_owned(), false)];
        let mut packages: Vec<String> = Vec::new();
        for _ in 0..self.count(MODULES_MAX - 1, 0) {
            if packages.is_empty() {
                packages.push(PACKAGE.to_owned());
                modules.push(Module::new(PACKAGE.to_owned(), true));
                continue;
            }
            let parent = self.random.choice(&packages);
            let name = format!("{parent}.{}", self.fresh("m"));
            let package = self.chance();
            if package {
                packages.push(name.clone());
            }
            modules.push(Module::new(name, package));
        }
        modules
    }

    fn plan(&mut self, module: &mut Module) {
        for _ in 0..self.count(DEFINITIONS_PER_MODULE_MAX, 1) {
            let kind = self.random.choice(&DEFINITION_KINDS);
            let names = match kind {
                Definition::Diamond => {
                    let names: Vec<String> = (0..4).map(|_| self.fresh("C")).collect();
                    module.exports.classes.extend(names.iter().cloned());
                    names
                }
                Definition::Class => {
                    let names = vec![self.fresh("C")];
                    module.exports.classes.extend(names.iter().cloned());
                    names
                }
                Definition::Value => {
                    let names = vec![self.fresh("v")];
                    module.exports.values.extend(names.iter().cloned());
                    names
                }
                Definition::Decorator => {
                    let names = vec![self.fresh("deco")];
                    module.exports.decorators.extend(names.iter().cloned());
                    names
                }
                Definition::Factory => {
                    let names = vec![self.fresh("factory")];
                    module.exports.factories.extend(names.iter().cloned());
                    names
                }
                Definition::Function => {
                    let names = vec![self.fresh("f")];
                    module.exports.functions.extend(names.iter().cloned());
                    names
                }
            };
            module.definitions.push((kind, names));
        }
    }

    fn module(&mut self, index: usize, modules: &[Module]) -> String {
        self.lines.clear();
        self.indent = 0;
        for line in HEADER {
            self.emit(line);
        }
        let module = &modules[index];
        let mut refs = Exports::default();
        refs.merge(&module.exports);
        let others: Vec<usize> = (0..modules.len()).filter(|&other| other != index).collect();
        for _ in 0..self.count(IMPORTS_PER_MODULE_MAX.min(others.len()), 0) {
            let target = self.random.choice(&others);
            let imported = self.import(module, &modules[target]);
            refs.merge(&imported);
        }
        let context = Context::new(
            Rc::new(refs),
            Scope::default(),
            Rc::new(module.exports.values.clone()),
        );
        for (kind, names) in &module.definitions {
            self.definition(&context, *kind, names);
        }
        self.block(&context, 0);
        if module.name == "main" {
            self.emit("if __name__ == \"__main__\":");
            self.indent += 1;
            self.block(&context, 1);
            self.indent -= 1;
        }
        self.lines.join("\n") + "\n"
    }

    fn import(&mut self, module: &Module, target: &Module) -> Exports {
        let exports = &target.exports;
        let names = exports.names();
        let mut forms = vec!["import", "import as", "from", "star"];
        if !target.package && target.name.contains('.') {
            forms.push("from package");
        }
        let relative = relative(module, target);
        if relative.is_some() {
            forms.push("relative");
        }
        let form = self.random.choice(&forms);
        match form {
            "import" => {
                self.emit(&format!("import {}", target.name));
                return exports.qualified(&target.name);
            }
            "import as" => {
                let alias = self.fresh("mod");
                self.emit(&format!("import {} as {alias}", target.name));
                return exports.qualified(&alias);
            }
            "from package" => {
                let (parent, leaf) = target.name.rsplit_once('.').expect("a dotted name");
                self.emit(&format!("from {parent} import {leaf}"));
                return exports.qualified(leaf);
            }
            "star" => {
                self.emit(&format!("from {} import *", target.name));
                return exports.clone();
            }
            _ => {}
        }
        let source = if form == "from" {
            target.name.clone()
        } else {
            relative.expect("a relative name")
        };
        let count = self.count(names.len(), 1);
        let chosen = self.random.sample(&names, count);
        let mut aliases: Vec<(String, String)> = Vec::new();
        for name in &chosen {
            let alias = self.alias(name);
            aliases.push((name.clone(), alias));
        }
        let imported: Vec<String> = aliases
            .iter()
            .map(|(name, alias)| {
                if alias == name {
                    name.clone()
                } else {
                    format!("{name} as {alias}")
                }
            })
            .collect();
        self.emit(&format!("from {source} import {}", imported.join(", ")));
        Exports::from_lists(
            |names| {
                names
                    .iter()
                    .filter_map(|name| {
                        aliases
                            .iter()
                            .find(|(chosen, _)| chosen == name)
                            .map(|(_, alias)| alias.clone())
                    })
                    .collect()
            },
            exports,
        )
    }

    fn alias(&mut self, name: &str) -> String {
        if self.chance() {
            return name.to_owned();
        }
        self.fresh(&format!(
            "{}_as",
            name.trim_end_matches(|c: char| c.is_ascii_digit())
        ))
    }

    fn definition(&mut self, context: &Context, kind: Definition, names: &[String]) {
        match kind {
            Definition::Class => {
                let bases = self.bases(context);
                self.class(context, &names[0], &bases, 0);
            }
            Definition::Diamond => {
                let (top, left, right, bottom) = (&names[0], &names[1], &names[2], &names[3]);
                self.class(context, top, &[], 0);
                self.class(context, left, std::slice::from_ref(top), 0);
                self.class(context, right, std::slice::from_ref(top), 0);
                self.class(context, bottom, &[left.clone(), right.clone()], 0);
            }
            Definition::Value => {
                let value = self.container(context, 1);
                self.emit(&format!("{} = {value}", names[0]));
            }
            Definition::Decorator => self.decorator(context, &names[0]),
            Definition::Factory => self.factory(context, &names[0]),
            Definition::Function => {
                let kind = self.random.choice(&FUNCTION_KINDS);
                let decorators = self.decorators(context, kind);
                self.function(context, &names[0], kind, &decorators, "", false, 0);
            }
        }
    }

    fn bases(&mut self, context: &Context) -> Vec<String> {
        let classes = context.refs.classes.clone();
        if classes.is_empty() {
            return Vec::new();
        }
        let count = self.count(BASES_PER_CLASS_MAX.min(classes.len()), 0);
        self.random.sample(&classes, count)
    }

    fn decorators(&mut self, context: &Context, kind: Kind) -> Vec<String> {
        let mut options: Vec<String> = context
            .refs
            .decorators
            .iter()
            .map(|name| format!("@{name}"))
            .collect();
        for name in context.refs.factories.clone() {
            let arguments = self.arguments(context, EXPRESSION_DEPTH_MAX - 1);
            options.push(format!("@{name}({arguments})"));
        }
        options.push("@functools.cache".to_owned());
        if kind == Kind::Generator {
            options.push("@contextlib.contextmanager".to_owned());
        }
        let count = self.count(2.min(options.len()), 0);
        self.random.sample(&options, count)
    }

    fn decorator(&mut self, context: &Context, name: &str) {
        let function = self.fresh("fn");
        self.emit(&format!("def {name}({function}):"));
        self.indent += 1;
        self.wrapper(context, &function, vec![function.clone()]);
        self.indent -= 1;
    }

    fn factory(&mut self, context: &Context, name: &str) {
        let parameter = self.fresh("p");
        let function = self.fresh("fn");
        let inner = self.fresh("decorate");
        self.emit(&format!("def {name}({parameter}=None):"));
        self.indent += 1;
        self.emit(&format!("def {inner}({function}):"));
        self.indent += 1;
        self.wrapper(context, &function, vec![parameter, function.clone()]);
        self.indent -= 1;
        self.emit(&format!("return {inner}"));
        self.indent -= 1;
    }

    fn wrapper(&mut self, context: &Context, function: &str, scope: Vec<String>) {
        let wrapper = self.fresh("wrapper");
        let args = self.fresh("args");
        let kwargs = self.fresh("kwargs");
        if self.chance() {
            self.emit(&format!("@functools.wraps({function})"));
        }
        self.emit(&format!("def {wrapper}(*{args}, **{kwargs}):"));
        self.indent += 1;
        let mut outer = context.outer.clone();
        outer.extend(scope.iter().cloned());
        let mut inner = Context::new(
            context.refs.clone(),
            Scope {
                variables: vec![args.clone(), kwargs.clone()],
                globals: Vec::new(),
            },
            context.module_values.clone(),
        );
        inner.outer = outer;
        inner.enclosing = scope;
        inner.kind = Kind::Plain;
        self.block(&inner, 1);
        self.emit(&format!("return {function}(*{args}, **{kwargs})"));
        self.indent -= 1;
        self.emit(&format!("return {wrapper}"));
    }

    fn class(&mut self, context: &Context, name: &str, bases: &[String], depth: usize) {
        for decorator in self.class_decorators(context) {
            self.emit(&decorator);
        }
        if bases.is_empty() {
            self.emit(&format!("class {name}:"));
        } else {
            self.emit(&format!("class {name}({}):", bases.join(", ")));
        }
        self.indent += 1;
        let mut outer = context.outer.clone();
        if context.kind.function() {
            outer.extend(context.scope.borrow().variables.iter().cloned());
        }
        let mut body = Context::new(
            context.refs.clone(),
            Scope::default(),
            context.module_values.clone(),
        );
        body.outer = outer;
        body.kind = Kind::Class;
        let attribute = self.random.choice(&ATTRIBUTE_NAMES);
        let value = self.expression(&body, 1);
        self.emit(&format!("{attribute} = {value}"));
        let count = self.count(METHODS_PER_CLASS_MAX, 1);
        let kinds = self.random.sample(&METHOD_KINDS, count);
        for kind in kinds {
            self.method(&body, name, kind, depth + 1);
        }
        self.indent -= 1;
    }

    fn class_decorators(&mut self, context: &Context) -> Vec<String> {
        let options: Vec<String> = context
            .refs
            .decorators
            .iter()
            .map(|name| format!("@{name}"))
            .collect();
        let count = self.count(1.min(options.len()), 0);
        self.random.sample(&options, count)
    }

    fn method(&mut self, body: &Context, owner: &str, kind: Method, depth: usize) {
        let mut method = body.clone();
        method.owner = Some(owner.to_owned());
        method.depth = depth;
        match kind {
            Method::Init => self.function(&method, "__init__", Kind::Plain, &[], "self", true, 0),
            Method::Plain => {
                let name = self.random.choice(&METHOD_NAMES);
                let kind = self.random.choice(&FUNCTION_KINDS);
                self.function(&method, name, kind, &[], "self", false, 0);
            }
            Method::Property => {
                let name = self.random.choice(&ATTRIBUTE_NAMES);
                self.function(
                    &method,
                    name,
                    Kind::Plain,
                    &["@property".to_owned()],
                    "self",
                    false,
                    0,
                );
                let setter = [format!("@{name}.setter")];
                self.function(&method, name, Kind::Plain, &setter, "self", false, 1);
            }
            Method::Static => {
                let name = self.random.choice(&METHOD_NAMES);
                self.function(
                    &method,
                    name,
                    Kind::Plain,
                    &["@staticmethod".to_owned()],
                    "",
                    false,
                    0,
                );
            }
            Method::OfClass => {
                let name = self.random.choice(&METHOD_NAMES);
                self.function(
                    &method,
                    name,
                    Kind::Plain,
                    &["@classmethod".to_owned()],
                    "cls",
                    false,
                    0,
                );
            }
            Method::Call => self.function(&method, "__call__", Kind::Plain, &[], "self", false, 0),
            Method::Getattr => {
                self.function(&method, "__getattr__", Kind::Plain, &[], "self", false, 1)
            }
            Method::Getitem => {
                self.function(&method, "__getitem__", Kind::Plain, &[], "self", false, 1)
            }
            Method::Iter => {
                self.function(&method, "__iter__", Kind::Generator, &[], "self", false, 0)
            }
            Method::Context => {
                self.function(&method, "__enter__", Kind::Plain, &[], "self", false, 0);
                self.function(&method, "__exit__", Kind::Plain, &[], "self", false, 3);
            }
            Method::Async => {
                self.function(&method, "__aenter__", Kind::Async, &[], "self", false, 0);
                self.function(&method, "__aexit__", Kind::Async, &[], "self", false, 3);
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    fn function(
        &mut self,
        context: &Context,
        name: &str,
        kind: Kind,
        decorators: &[String],
        first: &str,
        init: bool,
        minimum: usize,
    ) {
        let depth = context.depth + 1;
        let (parameters, names) = self.parameters(context, first, minimum);
        for decorator in decorators {
            self.emit(decorator);
        }
        let keyword = if kind.asynchronous() {
            "async def"
        } else {
            "def"
        };
        self.emit(&format!("{keyword} {name}({parameters}):"));
        self.indent += 1;
        let mut outer = context.outer.clone();
        let mut enclosing = Vec::new();
        if context.kind.function() {
            let variables = context.scope.borrow().variables.clone();
            outer.extend(variables.iter().cloned());
            enclosing = variables;
        }
        let mut inner = Context::new(
            context.refs.clone(),
            Scope {
                variables: names,
                globals: Vec::new(),
            },
            context.module_values.clone(),
        );
        inner.outer = outer;
        inner.enclosing = enclosing;
        inner.kind = kind;
        inner.owner = context.owner.clone();
        inner.depth = depth;
        self.declarations(&inner);
        if init && self.chance() {
            let arguments = self.arguments(&inner, 1);
            self.emit(&format!("super().__init__({arguments})"));
        }
        if init && !first.is_empty() {
            let count = self.count(2, 1);
            for attribute in self.random.sample(&ATTRIBUTE_NAMES, count) {
                let value = self.expression(&inner, 1);
                self.emit(&format!("{first}.{attribute} = {value}"));
            }
        }
        self.block(&inner, depth);
        if kind.yielding() {
            let value = self.expression(&inner, 1);
            self.emit(&format!("yield {value}"));
        } else if !init {
            let value = self.expression(&inner, 1);
            self.emit(&format!("return {value}"));
        }
        self.indent -= 1;
    }

    fn declarations(&mut self, context: &Context) {
        if !context.enclosing.is_empty() && self.chance() {
            let names = self.random.sample(&context.enclosing, 1);
            self.emit(&format!("nonlocal {}", names.join(", ")));
            context.scope.borrow_mut().globals.extend(names);
        }
        if !context.module_values.is_empty() && self.chance() {
            let names = self.random.sample(&context.module_values, 1);
            self.emit(&format!("global {}", names.join(", ")));
            context.scope.borrow_mut().globals.extend(names);
        }
    }

    fn parameters(
        &mut self,
        context: &Context,
        first: &str,
        minimum: usize,
    ) -> (String, Vec<String>) {
        let mut parts: Vec<String> = Vec::new();
        let mut names: Vec<String> = Vec::new();
        if !first.is_empty() {
            parts.push(first.to_owned());
            names.push(first.to_owned());
        }
        let count = self.count(PARAMETERS_PER_KIND_MAX + minimum, minimum);
        let positional: Vec<String> = (0..count).map(|_| self.fresh("p")).collect();
        let defaults_from = self.count(count, minimum);
        for (index, name) in positional.iter().enumerate() {
            if index < defaults_from {
                parts.push(name.clone());
            } else {
                let value = self.expression(context, 2);
                parts.push(format!("{name}={value}"));
            }
        }
        names.extend(positional.iter().cloned());
        if !parts.is_empty() && self.chance() {
            parts.push("/".to_owned());
        }
        let args = self.fresh("args");
        let star = self.random.choice(&[String::new(), "*".to_owned(), args]);
        let mut keywords = Vec::new();
        if !star.is_empty() {
            let count = self.count(PARAMETERS_PER_KIND_MAX, 0);
            keywords = (0..count).map(|_| self.fresh("k")).collect();
        }
        if star == "*" && keywords.is_empty() {
            keywords.push(self.fresh("k"));
        }
        if !star.is_empty() {
            parts.push(if star == "*" {
                "*".to_owned()
            } else {
                format!("*{star}")
            });
        }
        if star != "*" && !star.is_empty() {
            names.push(star.clone());
        }
        for name in &keywords {
            if self.chance() {
                let value = self.expression(context, 2);
                parts.push(format!("{name}={value}"));
            } else {
                parts.push(name.clone());
            }
        }
        names.extend(keywords);
        if self.chance() {
            let kwargs = self.fresh("kwargs");
            parts.push(format!("**{kwargs}"));
            names.push(kwargs);
        }
        (parts.join(", "), names)
    }

    fn block(&mut self, context: &Context, depth: usize) {
        for _ in 0..self.count(STATEMENTS_PER_BLOCK_MAX, 1) {
            self.statement(context, depth);
        }
    }

    fn nested(&mut self, context: &Context, depth: usize) {
        self.indent += 1;
        self.block(context, depth + 1);
        self.indent -= 1;
    }

    fn statement(&mut self, context: &Context, depth: usize) {
        let mut makers = vec![
            Statement::Assignment,
            Statement::Assignment,
            Statement::Unpacking,
            Statement::Expression,
            Statement::Expression,
            Statement::Reflection,
            Statement::Augmented,
            Statement::Annotated,
            Statement::Raise,
        ];
        if context.kind.function() && !context.cleanup {
            makers.push(Statement::Return);
        }
        if context.kind.yielding() {
            makers.push(Statement::Yield);
        }
        if context.looping && !context.cleanup {
            makers.push(Statement::Jump);
        }
        if depth < BLOCK_DEPTH_MAX {
            makers.extend([
                Statement::If,
                Statement::For,
                Statement::While,
                Statement::Try,
                Statement::With,
                Statement::Match,
                Statement::NestedFunction,
                Statement::NestedClass,
            ]);
        }
        match self.random.choice(&makers) {
            Statement::Assignment => self.assignment(context),
            Statement::Unpacking => self.unpacking(context),
            Statement::Expression => {
                let expression = if self.chance() {
                    self.call(context, 1)
                } else {
                    self.method_call(context, 1)
                };
                self.emit(&expression);
            }
            Statement::Reflection => {
                let name = self.name(context);
                let attribute = self.attribute_name(context);
                let value = self.expression(context, 1);
                self.emit(&format!("setattr({name}, {attribute}, {value})"));
            }
            Statement::Augmented => self.augmented(context),
            Statement::Annotated => self.annotated(context),
            Statement::Raise => self.raise(context),
            Statement::Return => {
                if context.kind == Kind::AsyncGenerator {
                    self.emit("return");
                } else {
                    let value = self.expression(context, 0);
                    self.emit(&format!("return {value}"));
                }
            }
            Statement::Yield => self.yield_statement(context),
            Statement::Jump => {
                let jump = self.random.choice(&["break", "continue"]);
                self.emit(jump);
            }
            Statement::If => self.if_statement(context, depth),
            Statement::For => self.for_statement(context, depth),
            Statement::While => {
                let test = self.expression(context, 1);
                self.emit(&format!("while {test}:"));
                let mut looping = context.clone();
                looping.looping = true;
                self.nested(&looping, depth);
                self.indent += 1;
                self.emit("break");
                self.indent -= 1;
            }
            Statement::Try => self.try_statement(context, depth),
            Statement::With => self.with_statement(context, depth),
            Statement::Match => self.match_statement(context, depth),
            Statement::NestedFunction => {
                let name = self.fresh("g");
                let kind = self.random.choice(&FUNCTION_KINDS);
                let decorators = self.decorators(context, kind);
                let mut inner = context.clone();
                inner.looping = false;
                inner.depth = depth;
                self.function(&inner, &name, kind, &decorators, "", false, 0);
                context.add(&[name]);
            }
            Statement::NestedClass => {
                let name = self.fresh("K");
                let bases = self.bases(context);
                self.class(context, &name, &bases, depth);
                context.add(&[name]);
            }
        }
    }

    fn assignment(&mut self, context: &Context) {
        let value = self.expression(context, 0);
        let assigned = context.assigned();
        let mut targets = Vec::new();
        let mut new = Vec::new();
        for _ in 0..self.count(2, 1) {
            let form = self
                .random
                .choice(&["new", "new", "old", "attribute", "subscript"]);
            if form == "old" && !assigned.is_empty() {
                targets.push(self.random.choice(&assigned));
            } else if form == "attribute" {
                let name = self.name(context);
                let attribute = self.random.choice(&ATTRIBUTE_NAMES);
                targets.push(format!("{name}.{attribute}"));
            } else if form == "subscript" {
                let index = self.expression(context, EXPRESSION_DEPTH_MAX - 1);
                let name = self.name(context);
                targets.push(format!("{name}[{index}]"));
            } else {
                let name = self.fresh("x");
                new.push(name.clone());
                targets.push(name);
            }
        }
        self.emit(&format!("{} = {value}", targets.join(" = ")));
        context.add(&new);
    }

    fn unpacking(&mut self, context: &Context) {
        let value = self.expression(context, 0);
        let (target, names) = self.unpacking_target();
        self.emit(&format!("{target} = {value}"));
        context.add(&names);
    }

    fn unpacking_target(&mut self) -> (String, Vec<String>) {
        let count = self.count(3, 2);
        let names: Vec<String> = (0..count).map(|_| self.fresh("x")).collect();
        match self.random.choice(&["tuple", "starred", "nested", "list"]) {
            "starred" => {
                let star = self.random.below(names.len());
                let parts: Vec<String> = names
                    .iter()
                    .enumerate()
                    .map(|(index, name)| {
                        if index == star {
                            format!("*{name}")
                        } else {
                            name.clone()
                        }
                    })
                    .collect();
                (parts.join(", "), names)
            }
            "nested" => {
                let rest = if names.len() > 2 {
                    names[2..].join(", ")
                } else {
                    "_".to_owned()
                };
                (format!("({}, {}), {rest}", names[0], names[1]), names)
            }
            "list" => (format!("[{}]", names.join(", ")), names),
            _ => (names.join(", "), names),
        }
    }

    fn augmented(&mut self, context: &Context) {
        let assigned = context.assigned();
        if assigned.is_empty() {
            self.assignment(context);
            return;
        }
        let operator = self.random.choice(&["+=", "|=", "-="]);
        let target = self.random.choice(&assigned);
        let value = self.expression(context, 1);
        self.emit(&format!("{target} {operator} {value}"));
    }

    fn annotated(&mut self, context: &Context) {
        let name = self.fresh("x");
        let mut annotations = context.refs.classes.clone();
        annotations.extend(BUILTIN_CLASSES.map(str::to_owned));
        annotations.push("list[int]".to_owned());
        let annotation = self.random.choice(&annotations);
        let value = self.expression(context, 0);
        self.emit(&format!("{name}: {annotation} = {value}"));
        context.add(&[name]);
    }

    fn raise(&mut self, context: &Context) {
        let mut exceptions: Vec<String> = EXCEPTIONS.map(str::to_owned).to_vec();
        exceptions.extend(context.refs.classes.iter().cloned());
        let exception = self.random.choice(&exceptions);
        let cause = self.random.choice(&[
            String::new(),
            " from None".to_owned(),
            format!(" from {exception}()"),
        ]);
        let arguments = self.arguments(context, 2);
        self.emit(&format!("raise {exception}({arguments}){cause}"));
    }

    fn yield_statement(&mut self, context: &Context) {
        let mut forms = vec!["yield", "assign"];
        if context.kind == Kind::Generator {
            forms.push("from");
        }
        let form = self.random.choice(&forms);
        let value = self.expression(context, 1);
        match form {
            "from" => self.emit(&format!("yield from {value}")),
            "assign" => {
                let name = self.fresh("x");
                self.emit(&format!("{name} = yield {value}"));
                context.add(&[name]);
            }
            _ => self.emit(&format!("yield {value}")),
        }
    }

    fn if_statement(&mut self, context: &Context, depth: usize) {
        let test = self.class_test(context, 1);
        self.emit(&format!("if {test}:"));
        self.nested(context, depth);
        if self.chance() {
            let test = self.expression(context, 1);
            self.emit(&format!("elif {test}:"));
            self.nested(context, depth);
        }
        if self.chance() {
            self.emit("else:");
            self.nested(context, depth);
        }
    }

    fn for_statement(&mut self, context: &Context, depth: usize) {
        let iterable = self.expression(context, 0);
        let (target, names) = if self.chance() {
            self.unpacking_target()
        } else {
            let name = self.fresh("x");
            (name.clone(), vec![name])
        };
        let asynchronous = context.kind.asynchronous() && self.chance();
        let keyword = if asynchronous { "async for" } else { "for" };
        self.emit(&format!("{keyword} {target} in {iterable}:"));
        context.add(&names);
        let mut looping = context.clone();
        looping.looping = true;
        self.nested(&looping, depth);
        if self.chance() {
            self.emit("else:");
            self.nested(context, depth);
        }
    }

    fn try_statement(&mut self, context: &Context, depth: usize) {
        self.emit("try:");
        self.nested(context, depth);
        let handlers = self.count(2, 0);
        for _ in 0..handlers {
            let mut exceptions: Vec<String> = EXCEPTIONS.map(str::to_owned).to_vec();
            exceptions.extend(context.refs.classes.iter().cloned());
            let count = self.count(2, 1);
            let caught = self.random.sample(&exceptions, count);
            let clause = if caught.len() == 1 {
                caught[0].clone()
            } else {
                format!("({})", caught.join(", "))
            };
            if self.chance() {
                let name = self.fresh("error");
                self.emit(&format!("except {clause} as {name}:"));
                context.add(&[name]);
            } else {
                self.emit(&format!("except {clause}:"));
            }
            self.nested(context, depth);
        }
        if handlers > 0 && self.chance() {
            self.emit("else:");
            self.nested(context, depth);
        }
        if handlers == 0 || self.chance() {
            self.emit("finally:");
            let mut cleanup = context.clone();
            cleanup.cleanup = true;
            self.nested(&cleanup, depth);
        }
    }

    fn with_statement(&mut self, context: &Context, depth: usize) {
        let mut items = Vec::new();
        let mut names = Vec::new();
        for _ in 0..self.count(2, 1) {
            let manager = self.expression(context, 1);
            if self.chance() {
                let name = self.fresh("x");
                items.push(format!("{manager} as {name}"));
                names.push(name);
            } else {
                items.push(manager);
            }
        }
        let asynchronous = context.kind.asynchronous() && self.chance();
        let keyword = if asynchronous { "async with" } else { "with" };
        self.emit(&format!("{keyword} {}:", items.join(", ")));
        context.add(&names);
        self.nested(context, depth);
    }

    fn match_statement(&mut self, context: &Context, depth: usize) {
        let subject = self.expression(context, 1);
        self.emit(&format!("match {subject}:"));
        self.indent += 1;
        for _ in 0..self.count(CASES_PER_MATCH_MAX, 1) {
            let mut names = Vec::new();
            let mut pattern = self.pattern(context, &mut names, 0);
            if self.chance() {
                let name = self.fresh("x");
                pattern = format!("({pattern}) as {name}");
                names.push(name);
            }
            context.add(&names);
            let guard = if self.chance() {
                format!(" if {}", self.expression(context, 1))
            } else {
                String::new()
            };
            self.emit(&format!("case {pattern}{guard}:"));
            self.nested(context, depth);
        }
        if self.chance() {
            let fresh = self.fresh("x");
            let name = self.random.choice(&["_".to_owned(), fresh]);
            self.emit(&format!("case {name}:"));
            if name != "_" {
                context.add(&[name]);
            }
            self.nested(context, depth);
        }
        self.indent -= 1;
    }

    fn pattern(&mut self, context: &Context, names: &mut Vec<String>, depth: usize) -> String {
        let mut forms = vec!["literal", "alternatives", "class", "sequence", "mapping"];
        if depth > 0 {
            forms.extend(["capture", "wildcard"]);
        }
        if depth >= PATTERN_DEPTH_MAX {
            forms = vec!["literal", "capture", "wildcard"];
        }
        match self.random.choice(&forms) {
            "literal" => self
                .random
                .choice(&["0", "'k'", "None", "True", "-1"])
                .to_owned(),
            "capture" => {
                let name = self.fresh("x");
                names.push(name.clone());
                name
            }
            "wildcard" => "_".to_owned(),
            "alternatives" => {
                let mut classes = context.refs.classes.clone();
                classes.extend(BUILTIN_CLASSES.map(str::to_owned));
                let chosen = self.random.sample(&classes, 2);
                let alternatives: Vec<String> =
                    chosen.iter().map(|name| format!("{name}()")).collect();
                alternatives.join(" | ")
            }
            "class" => {
                let mut classes = context.refs.classes.clone();
                classes.extend(BUILTIN_CLASSES.map(str::to_owned));
                let name = self.random.choice(&classes);
                let count = self.count(2, 0);
                let mut parts: Vec<String> = (0..count)
                    .map(|_| self.pattern(context, names, depth + 1))
                    .collect();
                let count = self.count(2, 0);
                for keyword in self.random.sample(&ATTRIBUTE_NAMES, count) {
                    let pattern = self.pattern(context, names, depth + 1);
                    parts.push(format!("{keyword}={pattern}"));
                }
                format!("{name}({})", parts.join(", "))
            }
            "sequence" => {
                let count = self.count(2, 0);
                let mut parts: Vec<String> = (0..count)
                    .map(|_| self.pattern(context, names, depth + 1))
                    .collect();
                if self.chance() {
                    let rest = self.fresh("rest");
                    parts.push(format!("*{rest}"));
                    names.push(rest);
                }
                format!("[{}]", parts.join(", "))
            }
            _ => {
                let count = self.count(2, 0);
                let keys = self.random.sample(&["'k'", "'run'", "0", "None"], count);
                let mut parts = Vec::new();
                for key in keys {
                    let pattern = self.pattern(context, names, depth + 1);
                    parts.push(format!("{key}: {pattern}"));
                }
                if self.chance() {
                    let rest = self.fresh("rest");
                    parts.push(format!("**{rest}"));
                    names.push(rest);
                }
                format!("{{{}}}", parts.join(", "))
            }
        }
    }

    fn expression(&mut self, context: &Context, depth: usize) -> String {
        if depth >= EXPRESSION_DEPTH_MAX {
            return self.atom(context);
        }
        let mut makers = vec![
            Expression::Atom,
            Expression::Call,
            Expression::Call,
            Expression::MethodCall,
            Expression::Attribute,
            Expression::Subscript,
            Expression::Container,
            Expression::Comprehension,
            Expression::Lambda,
            Expression::Reflection,
            Expression::ClassTest,
            Expression::Conditional,
            Expression::Builtin,
            Expression::Operation,
        ];
        if context.kind.asynchronous() {
            makers.push(Expression::Await);
        }
        if context.owner.is_some() {
            makers.push(Expression::SuperCall);
        }
        let depth = depth + 1;
        match self.random.choice(&makers) {
            Expression::Atom => self.atom(context),
            Expression::Call => self.call(context, depth),
            Expression::MethodCall => self.method_call(context, depth),
            Expression::Attribute => {
                let mut attributes: Vec<&str> = ATTRIBUTE_NAMES.to_vec();
                attributes.extend(METHOD_NAMES);
                let attribute = self.random.choice(&attributes);
                format!("{}.{attribute}", self.name(context))
            }
            Expression::Subscript => {
                if self.chance() {
                    format!("{}[1:]", self.name(context))
                } else {
                    let name = self.name(context);
                    format!("{name}[{}]", self.expression(context, depth))
                }
            }
            Expression::Container => self.container(context, depth),
            Expression::Comprehension => self.comprehension(context, depth),
            Expression::Lambda => {
                let (parameters, names) = self.parameters(context, "", 0);
                let mut inner = context.clone();
                inner.outer.extend(names);
                inner.kind = Kind::Plain;
                let body = self.expression(&inner, depth);
                if parameters.is_empty() {
                    format!("(lambda: {body})")
                } else {
                    format!("(lambda {parameters}: {body})")
                }
            }
            Expression::Reflection => {
                let target = self.name(context);
                let attribute = self.attribute_name(context);
                match self.random.choice(&["getattr", "default", "hasattr"]) {
                    "getattr" => format!("getattr({target}, {attribute})"),
                    "default" => {
                        let default = self.expression(context, depth);
                        format!("getattr({target}, {attribute}, {default})")
                    }
                    _ => format!("hasattr({target}, {attribute})"),
                }
            }
            Expression::ClassTest => self.class_test(context, depth),
            Expression::Conditional => {
                let then = self.expression(context, depth);
                let test = self.expression(context, depth);
                let otherwise = self.expression(context, depth);
                format!("({then} if {test} else {otherwise})")
            }
            Expression::Builtin => self.builtin(context, depth),
            Expression::Operation => {
                let left = self.expression(context, depth);
                let right = self.expression(context, depth);
                let operator = self
                    .random
                    .choice(&["+", "|", "and", "or", "==", "in", "@"]);
                format!("({left} {operator} {right})")
            }
            Expression::Await => format!("(await {})", self.expression(context, depth)),
            Expression::SuperCall => {
                let mut methods: Vec<&str> = METHOD_NAMES.to_vec();
                methods.extend(["__init__", "__getattr__"]);
                let method = self.random.choice(&methods);
                format!("super().{method}({})", self.arguments(context, depth))
            }
        }
    }

    fn atom(&mut self, context: &Context) -> String {
        if self.chance() {
            return self.random.choice(&CONSTANTS).to_owned();
        }
        self.name(context)
    }

    fn name(&mut self, context: &Context) -> String {
        self.random.choice(&context.visible())
    }

    fn callee(&mut self, context: &Context) -> String {
        let callables = context.refs.callables();
        if callables.is_empty() {
            self.random.choice(&context.visible())
        } else {
            self.random.choice(&callables)
        }
    }

    fn arguments(&mut self, context: &Context, depth: usize) -> String {
        let count = self.count(ARGUMENTS_PER_CALL_MAX, 0);
        let mut parts: Vec<String> = (0..count)
            .map(|_| self.expression(context, depth))
            .collect();
        if self.chance() {
            parts.push(format!("*{}", self.expression(context, depth)));
        }
        let count = self.count(2, 0);
        for keyword in self.random.sample(&KEYWORD_NAMES, count) {
            parts.push(format!("{keyword}={}", self.expression(context, depth)));
        }
        if self.chance() {
            parts.push(format!("**{}", self.expression(context, depth)));
        }
        parts.join(", ")
    }

    fn call(&mut self, context: &Context, depth: usize) -> String {
        let callee = if self.chance() {
            self.callee(context)
        } else {
            self.name(context)
        };
        format!("{callee}({})", self.arguments(context, depth))
    }

    fn method_call(&mut self, context: &Context, depth: usize) -> String {
        let mut methods: Vec<&str> = METHOD_NAMES.to_vec();
        methods.extend(CONTAINER_METHODS);
        let method = self.random.choice(&methods);
        let name = self.name(context);
        format!("{name}.{method}({})", self.arguments(context, depth))
    }

    fn container(&mut self, context: &Context, depth: usize) -> String {
        let form = self.random.choice(&["list", "tuple", "set", "dict"]);
        let count = self.count(ELEMENTS_PER_CONTAINER_MAX, 1);
        let mut elements: Vec<String> = (0..count)
            .map(|_| self.expression(context, depth))
            .collect();
        if form != "dict" && self.chance() {
            elements.push(format!("*{}", self.expression(context, depth)));
        }
        match form {
            "list" => format!("[{}]", elements.join(", ")),
            "tuple" => format!("({},)", elements.join(", ")),
            "set" => format!("{{{}}}", elements.join(", ")),
            _ => {
                let mut items = Vec::new();
                for element in elements {
                    let key = self.random.choice(&CONSTANTS);
                    items.push(format!("{key}: {element}"));
                }
                if self.chance() {
                    items.push(format!("**{}", self.expression(context, depth)));
                }
                format!("{{{}}}", items.join(", "))
            }
        }
    }

    fn comprehension(&mut self, context: &Context, depth: usize) -> String {
        let iterable = self.expression(context, depth);
        let count = self.count(2, 1);
        let names: Vec<String> = (0..count).map(|_| self.fresh("i")).collect();
        let target = names.join(", ");
        let mut inner = context.clone();
        inner.outer.extend(names.iter().cloned());
        let element = self.expression(&inner, depth);
        let condition = if self.chance() {
            format!(" if {}", self.expression(&inner, depth))
        } else {
            String::new()
        };
        let clause = format!("for {target} in {iterable}{condition}");
        match self.random.choice(&["list", "set", "dict", "generator"]) {
            "list" => format!("[{element} {clause}]"),
            "set" => format!("{{{element} {clause}}}"),
            "dict" => format!("{{{}: {element} {clause}}}", names[0]),
            _ => format!("({element} {clause})"),
        }
    }

    fn attribute_name(&mut self, context: &Context) -> String {
        let mut attributes: Vec<&str> = ATTRIBUTE_NAMES.to_vec();
        attributes.extend(METHOD_NAMES);
        let constant = format!("'{}'", self.random.choice(&attributes));
        match self
            .random
            .choice(&["constant", "concatenated", "computed"])
        {
            "constant" => constant,
            "concatenated" => format!("{}' + '{}", &constant[..2], &constant[2..]),
            _ => self.name(context),
        }
    }

    fn class_test(&mut self, context: &Context, depth: usize) -> String {
        let mut classes = context.refs.classes.clone();
        classes.extend(BUILTIN_CLASSES.map(str::to_owned));
        let count = self.count(2, 1);
        let chosen = self.random.sample(&classes, count);
        let tested = if chosen.len() == 1 {
            chosen[0].clone()
        } else {
            format!("({})", chosen.join(", "))
        };
        format!("isinstance({}, {tested})", self.expression(context, depth))
    }

    fn builtin(&mut self, context: &Context, depth: usize) -> String {
        let value = self.expression(context, depth);
        let function = self.callee(context);
        let other = self.name(context);
        let forms = [
            format!("len({value})"),
            format!("sorted({value}, key={function})"),
            format!("list(map({function}, {value}))"),
            format!("filter({function}, {value})"),
            format!("next(iter({value}), None)"),
            format!("functools.partial({function}, {value})"),
            format!("dict({value})"),
            format!("zip({value}, {other})"),
            format!("enumerate({value})"),
            format!("type({value})"),
            format!("functools.reduce({function}, {value})"),
            format!("asyncio.run({function}({value}))"),
        ];
        self.random.choice(&forms)
    }
}

fn relative(module: &Module, target: &Module) -> Option<String> {
    let source = module.parent();
    let parts: Vec<&str> = target.name.split('.').collect();
    if source.is_empty() || target.package {
        return None;
    }
    let mut common = 0;
    while common < source.len() && common < parts.len() - 1 && source[common] == parts[common] {
        common += 1;
    }
    if common == 0 {
        return None;
    }
    let dots = ".".repeat(source.len() - common + 1);
    Some(dots + &parts[common..].join("."))
}
