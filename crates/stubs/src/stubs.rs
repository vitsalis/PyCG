use std::collections::{BTreeMap, BTreeSet};
use std::sync::Arc;

use rustc_hash::{FxHashMap, FxHashSet};

use crate::data;
use crate::entry::{Class, Decoder, Entry, EntryId, Module, ModuleId, Type, class_names};
use crate::mro::linearize;

pub const IMPLICIT_BASE: &str = "builtins.object";
pub const PROTOCOL_METACLASS: &str = "typing._ProtocolMeta";
pub const DEFAULT_METACLASS: &str = "builtins.type";
pub const ABC_MODULE: &str = "collections.abc";
pub const TYPING_MODULE: &str = "typing";
pub const RETURNS_SELF: &[(&str, &[(&str, &str)])] = &[(
    TYPING_MODULE,
    &[
        ("Iterator", "__iter__"),
        ("Generator", "__iter__"),
        ("AsyncIterator", "__aiter__"),
    ],
)];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum DefinitionKind {
    Module,
    Class,
    Function,
    Property,
    Variable,
}

impl DefinitionKind {
    pub fn name(self) -> &'static str {
        match self {
            DefinitionKind::Module => "module",
            DefinitionKind::Class => "class",
            DefinitionKind::Function => "function",
            DefinitionKind::Property => "property",
            DefinitionKind::Variable => "variable",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Definition {
    pub kind: DefinitionKind,
    pub path: Box<str>,
    pub entry: Option<EntryId>,
    pub owner: Option<Box<str>>,
}

impl PartialEq for Definition {
    fn eq(&self, other: &Self) -> bool {
        (self.kind, &self.path, &self.owner) == (other.kind, &other.path, &other.owner)
    }
}

impl Eq for Definition {}

impl std::hash::Hash for Definition {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        (self.kind, &self.path, &self.owner).hash(state);
    }
}

impl Definition {
    fn module(path: &str) -> Definition {
        Definition {
            kind: DefinitionKind::Module,
            path: Box::from(path),
            entry: None,
            owner: None,
        }
    }
}

type Mro = Arc<[Box<str>]>;
type Members = FxHashMap<Box<str>, Arc<[Definition]>>;
type PackageModules = BTreeMap<Box<str>, ModuleId>;

#[derive(Default)]
pub struct Stubs {
    entries: Vec<Entry>,
    modules: Vec<Module>,
    packages: FxHashMap<Box<str>, Option<PackageModules>>,
    module_by_name: FxHashMap<Box<str>, Option<ModuleId>>,
    definition_by_path: FxHashMap<Box<str>, Option<Definition>>,
    members_by_class_and_name: FxHashMap<Box<str>, Members>,
    mro_by_class: FxHashMap<Box<str>, Mro>,
    abstract_by_class: FxHashMap<Box<str>, bool>,
    abstract_reach_by_class: FxHashMap<Box<str>, Arc<BTreeSet<Box<str>>>>,
    abc_name_by_typing_path: Option<FxHashMap<Box<str>, Box<str>>>,
}

struct MroFrame {
    class: Box<str>,
    bases: Vec<Box<str>>,
    next: usize,
}

impl Stubs {
    pub fn new() -> Stubs {
        Stubs::default()
    }

    pub fn entry(&self, id: EntryId) -> &Entry {
        &self.entries[id.0 as usize]
    }

    pub fn module_data(&self, id: ModuleId) -> &Module {
        &self.modules[id.0 as usize]
    }

    fn class_entry(&self, definition: &Definition) -> Option<&Class> {
        match (definition.kind, definition.entry) {
            (DefinitionKind::Class, Some(id)) => match self.entry(id) {
                Entry::Class(class) => Some(class),
                _ => unreachable!("a class definition holds a class entry"),
            },
            _ => None,
        }
    }

    fn owner_class(&self, class: &str, owner: &str, definition: &Definition) -> &Class {
        match self.class_entry(definition) {
            Some(entry) => entry,
            None => panic!(
                "the MRO of {class} holds {owner}, a {}, not a class",
                definition.kind.name()
            ),
        }
    }

    fn package(&mut self, top: &str) -> Option<&BTreeMap<Box<str>, ModuleId>> {
        if !self.packages.contains_key(top) {
            let decoded = data::package_bytes(top).map(|bytes| self.decode(top, bytes));
            self.packages.insert(Box::from(top), decoded);
        }
        self.packages.get(top).and_then(Option::as_ref)
    }

    fn decode(&mut self, top: &str, bytes: &[u8]) -> BTreeMap<Box<str>, ModuleId> {
        let value: serde_json::Value = match serde_json::from_slice(bytes) {
            Ok(value) => value,
            Err(error) => panic!("embedded stub data {top}: {error}"),
        };
        let mut decoder = Decoder {
            entries: &mut self.entries,
            modules: &mut self.modules,
        };
        let modules = match decoder.package(&value, top) {
            Ok(modules) => modules,
            Err(error) => panic!("embedded stub data {top}: {error}"),
        };
        for (package, members) in RETURNS_SELF {
            if *package == top {
                self.read_result_as_self(&modules, top, members);
            }
        }
        modules
    }

    fn read_result_as_self(
        &mut self,
        modules: &BTreeMap<Box<str>, ModuleId>,
        top: &str,
        members: &[(&str, &str)],
    ) {
        let Some(&module) = modules.get(top) else {
            return;
        };
        for (class, method) in members {
            let Some(&class) = self.modules[module.0 as usize].names.get(*class) else {
                continue;
            };
            let Entry::Class(class) = &self.entries[class.0 as usize] else {
                continue;
            };
            let Some(&member) = class.members.get(*method) else {
                continue;
            };
            if let Entry::Function(function) = &mut self.entries[member.0 as usize] {
                for signature in function.signatures.iter_mut() {
                    signature.result = Type::SelfType;
                }
            }
        }
    }

    pub fn package_modules(&mut self, top: &str) -> Vec<(Box<str>, ModuleId)> {
        self.package(top)
            .map(|modules| {
                modules
                    .iter()
                    .map(|(name, &id)| (name.clone(), id))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn module(&mut self, name: &str) -> Option<ModuleId> {
        if let Some(found) = self.module_by_name.get(name) {
            return *found;
        }
        let top = name.split('.').next().expect("a split gives a first part");
        let found = self
            .package(top)
            .and_then(|modules| modules.get(name).copied());
        self.module_by_name.insert(Box::from(name), found);
        found
    }

    pub fn find(&mut self, path: &str) -> Vec<Definition> {
        let mut parts = path.split('.');
        let first = parts.next().expect("a split gives a first part");
        if self.module(first).is_none() {
            return Vec::new();
        }
        let mut found = vec![Definition::module(first)];
        for part in parts {
            let mut next = Vec::new();
            for base in &found {
                for definition in self.attribute(base, part).iter() {
                    if !next.contains(definition) {
                        next.push(definition.clone());
                    }
                }
            }
            found = next;
        }
        found
    }

    pub fn attribute(&mut self, definition: &Definition, name: &str) -> Arc<[Definition]> {
        match definition.kind {
            DefinitionKind::Module => {
                let Some(module) = self.module(&definition.path) else {
                    panic!(
                        "the module definition {} has no stub module",
                        definition.path
                    );
                };
                let path = format!("{}.{name}", definition.path);
                if let Some(&entry) = self.module_data(module).names.get(name) {
                    return Arc::from(self.follow(&path, entry, None));
                }
                if self.module(&path).is_some() {
                    return Arc::from([Definition::module(&path)]);
                }
                Arc::from([])
            }
            DefinitionKind::Class => {
                let found = self.member(&definition.path, name);
                if !found.is_empty() {
                    return found;
                }
                self.metaclass_member(&definition.path, name)
            }
            DefinitionKind::Function | DefinitionKind::Property | DefinitionKind::Variable => {
                Arc::from([])
            }
        }
    }

    pub fn metaclass_member(&mut self, class: &str, name: &str) -> Arc<[Definition]> {
        let metaclass = self.metaclass(class);
        self.member(&metaclass, name)
    }

    pub fn metaclass(&mut self, class: &str) -> Box<str> {
        let mut protocol = false;
        for owner in self.mro(class).iter() {
            let Some(definition) = self.definition(owner) else {
                continue;
            };
            assert!(
                definition.kind != DefinitionKind::Module,
                "the MRO of {class} holds the module {owner}"
            );
            let Some(entry) = self.class_entry(&definition) else {
                continue;
            };
            if let Some(metaclass) = &entry.metaclass
                && let Some(first) = class_names(metaclass).first()
            {
                return Box::from(*first);
            }
            if entry.protocol {
                protocol = true;
            }
        }
        Box::from(if protocol {
            PROTOCOL_METACLASS
        } else {
            DEFAULT_METACLASS
        })
    }

    pub fn member(&mut self, class: &str, name: &str) -> Arc<[Definition]> {
        if let Some(found) = self
            .members_by_class_and_name
            .get(class)
            .and_then(|members| members.get(name))
        {
            return found.clone();
        }
        let found: Arc<[Definition]> = Arc::from(self.find_member(class, name));
        self.members_by_class_and_name
            .entry(Box::from(class))
            .or_default()
            .insert(Box::from(name), found.clone());
        found
    }

    fn find_member(&mut self, class: &str, name: &str) -> Vec<Definition> {
        for owner in self.mro(class).iter() {
            let Some(definition) = self.definition(owner) else {
                continue;
            };
            let entry = self.owner_class(class, owner, &definition);
            if let Some(&member) = entry.members.get(name) {
                return self.follow(&format!("{owner}.{name}"), member, Some(owner));
            }
        }
        Vec::new()
    }

    pub fn definition(&mut self, path: &str) -> Option<Definition> {
        if let Some(found) = self.definition_by_path.get(path) {
            return found.clone();
        }
        let found = self.find_definition(path);
        self.definition_by_path
            .insert(Box::from(path), found.clone());
        found
    }

    fn find_definition(&mut self, path: &str) -> Option<Definition> {
        let mut module = path;
        let data = loop {
            if module.is_empty() {
                return None;
            }
            if let Some(data) = self.module(module) {
                break data;
            }
            module = module.rsplit_once('.').map_or("", |(parent, _)| parent);
        };
        if module == path {
            return Some(Definition::module(path));
        }
        let qualname: Vec<&str> = path[module.len() + 1..].split('.').collect();
        let mut names = &self.module_data(data).names;
        let mut owner = None;
        let mut entry = None;
        for (index, part) in qualname.iter().enumerate() {
            let found = *names.get(*part)?;
            entry = Some(found);
            if index < qualname.len() - 1 {
                let Entry::Class(class) = self.entry(found) else {
                    return None;
                };
                owner = Some(Box::from(format!(
                    "{module}.{}",
                    qualname[..=index].join(".")
                )));
                names = &class.members;
            }
        }
        let entry = entry.expect("a qualified name has a part");
        Some(Definition {
            kind: entry_kind(self.entry(entry))?,
            path: Box::from(path),
            entry: Some(entry),
            owner,
        })
    }

    fn follow(&mut self, path: &str, entry: EntryId, owner: Option<&str>) -> Vec<Definition> {
        let mut found = Vec::new();
        if let Some(kind) = entry_kind(self.entry(entry)) {
            found.push(Definition {
                kind,
                path: Box::from(path),
                entry: Some(entry),
                owner: owner.map(Box::from),
            });
        }
        let targets: Vec<(Box<str>, Box<str>)> = {
            let entry = self.entry(entry);
            entry
                .to()
                .iter()
                .chain(entry.also())
                .map(|target| (target.module.clone(), target.qualname.clone()))
                .collect()
        };
        for (module, qualname) in targets {
            if qualname.is_empty() {
                found.push(Definition::module(&module));
                continue;
            }
            if let Some(target) = self.definition(&format!("{module}.{qualname}")) {
                found.push(target);
            }
        }
        found
    }

    fn class_bases(&mut self, class: &str) -> Vec<Box<str>> {
        let mut bases = Vec::new();
        let names: Vec<Box<str>> = match self.definition(class) {
            Some(definition) => match self.class_entry(&definition) {
                Some(entry) => entry
                    .bases
                    .iter()
                    .flat_map(class_names)
                    .map(Box::from)
                    .collect(),
                None => Vec::new(),
            },
            None => Vec::new(),
        };
        for name in names {
            if let Some(target) = self.definition(&name)
                && target.kind == DefinitionKind::Class
            {
                bases.push(name);
            }
        }
        bases
    }

    fn start_mro(&mut self, class: &str) -> MroFrame {
        self.mro_by_class
            .insert(Box::from(class), Arc::from([Box::from(class)]));
        let mut bases = self.class_bases(class);
        if bases.is_empty() && class != IMPLICIT_BASE {
            bases.push(Box::from(IMPLICIT_BASE));
        }
        MroFrame {
            class: Box::from(class),
            bases,
            next: 0,
        }
    }

    pub fn mro(&mut self, class: &str) -> Mro {
        if let Some(found) = self.mro_by_class.get(class) {
            return found.clone();
        }
        let mut stack = vec![self.start_mro(class)];
        while let Some(frame) = stack.last_mut() {
            if frame.next < frame.bases.len() {
                let base = frame.bases[frame.next].clone();
                frame.next += 1;
                if !self.mro_by_class.contains_key(&base) {
                    let started = self.start_mro(&base);
                    stack.push(started);
                }
                continue;
            }
            let frame = stack.pop().expect("a frame on the stack");
            let memo = &self.mro_by_class;
            let mro: Mro = Arc::from(linearize(
                &frame.class,
                &frame.bases,
                |base| &memo[base][..],
            ));
            self.mro_by_class.insert(frame.class, mro);
        }
        self.mro_by_class[class].clone()
    }

    pub fn is_abstract(&mut self, class: &str) -> bool {
        if let Some(&found) = self.abstract_by_class.get(class) {
            return found;
        }
        let result = self.find_abstract(class);
        self.abstract_by_class.insert(Box::from(class), result);
        result
    }

    fn find_abstract(&mut self, class: &str) -> bool {
        let Some(definition) = self.definition(class) else {
            return true;
        };
        let Some(entry) = self.class_entry(&definition) else {
            return true;
        };
        let mut result = entry.protocol || entry.type_check_only;
        let mut seen: FxHashSet<Box<str>> = FxHashSet::default();
        for owner in self.mro(class).iter() {
            if result {
                break;
            }
            let Some(found) = self.definition(owner) else {
                continue;
            };
            let entry = self.owner_class(class, owner, &found);
            for (name, &member) in &entry.members {
                if seen.insert(name.clone()) {
                    result = result || self.entry(member).is_abstract();
                }
            }
        }
        result
    }

    pub fn abstract_reach(&mut self, class: &str) -> Arc<BTreeSet<Box<str>>> {
        if let Some(found) = self.abstract_reach_by_class.get(class) {
            return found.clone();
        }
        let mut reach: BTreeSet<Box<str>> = BTreeSet::new();
        let mut pending: Vec<Box<str>> = vec![Box::from(class)];
        while let Some(current) = pending.pop() {
            if reach.contains(&current) || !self.is_abstract(&current) {
                continue;
            }
            let bases = self.class_bases(&current);
            reach.insert(current);
            pending.extend(bases);
        }
        let reach = Arc::new(reach);
        self.abstract_reach_by_class
            .insert(Box::from(class), reach.clone());
        reach
    }

    pub fn abc_name(&mut self, path: &str) -> Option<Box<str>> {
        if self.abc_name_by_typing_path.is_none() {
            let mut names = FxHashMap::default();
            if let Some(module) = self.module(ABC_MODULE) {
                for (name, &entry) in &self.module_data(module).names {
                    for target in self.entry(entry).to() {
                        if &*target.module == TYPING_MODULE {
                            names.insert(
                                Box::from(format!("{TYPING_MODULE}.{}", target.qualname)),
                                Box::from(format!("{ABC_MODULE}.{name}")),
                            );
                        }
                    }
                }
            }
            self.abc_name_by_typing_path = Some(names);
        }
        self.abc_name_by_typing_path
            .as_ref()
            .and_then(|names| names.get(path).cloned())
    }

    pub fn public_name(&mut self, class: &str) -> Box<str> {
        let Some(definition) = self.definition(class) else {
            return Box::from(class);
        };
        match self.class_entry(&definition) {
            Some(entry) => entry
                .public_name
                .clone()
                .unwrap_or_else(|| Box::from(class)),
            None => Box::from(class),
        }
    }
}

fn entry_kind(entry: &Entry) -> Option<DefinitionKind> {
    match entry {
        Entry::Function(_) => Some(DefinitionKind::Function),
        Entry::Class(_) => Some(DefinitionKind::Class),
        Entry::Property(_) => Some(DefinitionKind::Property),
        Entry::Variable(_) => Some(DefinitionKind::Variable),
        Entry::Reference(_) => None,
    }
}
