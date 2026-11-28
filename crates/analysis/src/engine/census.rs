use std::fmt::Write as _;
use std::hash::{Hash, Hasher};
use std::mem::{Discriminant, discriminant, size_of};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use pycg_solver::ObjId;
use rustc_hash::{FxHashMap, FxHashSet, FxHasher};

use crate::engine::chains::Chain;
use crate::engine::objects::{Kind, Object};
use crate::engine::rules::{Rule, RuleId, WaitingRule};
use crate::engine::{Graph, State};

const CENSUS_RSS_GIB: [u64; 3] = [4, 8, 12];
const CENSUS_INTERVAL: Duration = Duration::from_secs(60);
const CENSUS_CHECK_STEPS: u64 = 1 << 16;
const KIB_PER_GIB: u64 = 1 << 20;
const KIB_PER_MIB: u64 = 1 << 10;
const RULE_NAME_BYTES: usize = 64;
const RULE_WRAPPERS: &[&str] = &[
    "Container",
    "Protocol",
    "Pattern",
    "Outside",
    "Annotation",
    "OutsideResult",
    "Library",
    "ClassTest",
];

type RuleKey = (Discriminant<Rule>, u64);

#[derive(Default)]
struct Applied {
    name: String,
    calls: u64,
    objects: u64,
    max_objects: u64,
    nanos: u128,
}

pub(crate) struct Census {
    start: Instant,
    last: Instant,
    steps: u64,
    checks: u64,
    check_nanos: u128,
    dumps: u64,
    dump_nanos: u128,
    thresholds_passed: usize,
    nesting: u32,
    applied: FxHashMap<RuleKey, Applied>,
    woken: FxHashMap<&'static str, Applied>,
    pub(crate) add_object: u64,
    pub(crate) add_edge: u64,
    pub(crate) call_bound: u64,
    pub(crate) call_function: u64,
    pub(crate) accessors_apply_receiver: u64,
    pub(crate) accessors_add_method: u64,
    pub(crate) rules_released: u64,
    pub(crate) rules_reused: u64,
}

impl Default for Census {
    fn default() -> Self {
        let now = Instant::now();
        Census {
            start: now,
            last: now,
            steps: 0,
            checks: 0,
            check_nanos: 0,
            dumps: 0,
            dump_nanos: 0,
            thresholds_passed: 0,
            nesting: 0,
            applied: FxHashMap::default(),
            woken: FxHashMap::default(),
            add_object: 0,
            add_edge: 0,
            call_bound: 0,
            call_function: 0,
            accessors_apply_receiver: 0,
            accessors_add_method: 0,
            rules_released: 0,
            rules_reused: 0,
        }
    }
}

struct Bounded(String);

impl std::fmt::Write for Bounded {
    fn write_str(&mut self, text: &str) -> std::fmt::Result {
        for c in text.chars() {
            if self.0.len() + c.len_utf8() > RULE_NAME_BYTES {
                return Err(std::fmt::Error);
            }
            self.0.push(c);
        }
        Ok(())
    }
}

fn rule_name(rule: &Rule) -> String {
    let mut text = Bounded(String::new());
    let _ = write!(text, "{rule:?}");
    let text = text.0;
    let identifier = |from: &str| -> String {
        from.chars()
            .take_while(|c| c.is_ascii_alphanumeric() || *c == '_')
            .collect()
    };
    let outer = identifier(&text);
    if RULE_WRAPPERS.contains(&outer.as_str()) && text[outer.len()..].starts_with('(') {
        let inner = identifier(&text[outer.len() + 1..]);
        return format!("{outer}({inner})");
    }
    outer
}

fn rule_key(rule: &Rule) -> RuleKey {
    let mut hasher = FxHasher::default();
    match rule {
        Rule::Container(inner) => discriminant(inner).hash(&mut hasher),
        Rule::Protocol(inner) => discriminant(&**inner).hash(&mut hasher),
        Rule::Pattern(inner) => discriminant(inner).hash(&mut hasher),
        Rule::Outside(inner) => discriminant(&**inner).hash(&mut hasher),
        Rule::Annotation(inner) => discriminant(&**inner).hash(&mut hasher),
        Rule::OutsideResult(inner) => discriminant(&**inner).hash(&mut hasher),
        Rule::Library(inner) => discriminant(inner).hash(&mut hasher),
        Rule::ClassTest(inner) => discriminant(&**inner).hash(&mut hasher),
        _ => {}
    }
    (discriminant(rule), hasher.finish())
}

fn waiting_name(rule: &WaitingRule) -> &'static str {
    match rule {
        WaitingRule::CallDunder { .. } => "CallDunder",
        WaitingRule::DeliverLoad(_) => "DeliverLoad",
        WaitingRule::CallHook { .. } => "CallHook",
        WaitingRule::FoundStore(_) => "FoundStore",
    }
}

fn rss_kib() -> u64 {
    let status = std::fs::read_to_string("/proc/self/status").expect("/proc/self/status");
    let line = status
        .lines()
        .find(|line| line.starts_with("VmRSS:"))
        .expect("a VmRSS line");
    let fields: Vec<&str> = line.split_whitespace().collect();
    assert_eq!(fields.get(2), Some(&"kB"), "VmRSS is in kB: {line}");
    fields[1].parse().expect("VmRSS is a number")
}

fn hist_bucket(length: usize) -> usize {
    match length {
        0 => 0,
        1..=10 => 1,
        11..=100 => 2,
        101..=1000 => 3,
        1001..=4999 => 4,
        _ => 5,
    }
}

fn map_bytes<K, V>(capacity: usize) -> usize {
    capacity * (size_of::<(K, V)>() + 1)
}

struct Held {
    holders: usize,
    nonempty: usize,
    elements: u64,
    max: u32,
    hist: [usize; 6],
    distinct_chains: FxHashSet<Chain>,
}

impl Held {
    fn new() -> Held {
        Held {
            holders: 0,
            nonempty: 0,
            elements: 0,
            max: 0,
            hist: [0; 6],
            distinct_chains: FxHashSet::default(),
        }
    }

    fn add(&mut self, chain: Chain, depth: &[u32]) {
        let length = depth[chain.0 as usize];
        self.holders += 1;
        if length > 0 {
            self.nonempty += 1;
        }
        self.elements += u64::from(length);
        self.max = self.max.max(length);
        self.hist[hist_bucket(length as usize)] += 1;
        self.distinct_chains.insert(chain);
    }

    fn line(&self) -> String {
        format!(
            "holders={} nonempty={} held_elements={} max={} hist(0,<=10,<=100,<=1k,<5k,>=5k)={:?} distinct_chains={}",
            self.holders,
            self.nonempty,
            self.elements,
            self.max,
            self.hist,
            self.distinct_chains.len()
        )
    }
}

struct Sets {
    hashes: FxHashMap<u64, usize>,
    duplicates: u64,
}

impl Sets {
    fn new() -> Sets {
        Sets {
            hashes: FxHashMap::default(),
            duplicates: 0,
        }
    }

    fn add(&mut self, mut objects: Vec<ObjId>) {
        let length = objects.len();
        objects.sort_unstable();
        objects.dedup();
        self.duplicates += (length - objects.len()) as u64;
        let mut hasher = FxHasher::default();
        objects.hash(&mut hasher);
        self.hashes.insert(hasher.finish(), objects.len());
    }

    fn line(&self) -> String {
        format!(
            "distinct_receiver_sets={} elements_if_shared={} duplicates_in_chains={}",
            self.hashes.len(),
            self.hashes.values().sum::<usize>(),
            self.duplicates
        )
    }
}

impl State {
    pub(super) fn census_step(&mut self, graph: &Graph) {
        self.census.steps += 1;
        if !self.census.steps.is_multiple_of(CENSUS_CHECK_STEPS) {
            return;
        }
        let started = Instant::now();
        self.census.checks += 1;
        let rss = rss_kib();
        let mut reason = None;
        while self.census.thresholds_passed < CENSUS_RSS_GIB.len()
            && rss >= CENSUS_RSS_GIB[self.census.thresholds_passed] * KIB_PER_GIB
        {
            reason = Some(format!(
                "rss>={}GiB",
                CENSUS_RSS_GIB[self.census.thresholds_passed]
            ));
            self.census.thresholds_passed += 1;
        }
        self.census.check_nanos += started.elapsed().as_nanos();
        if let Some(reason) = reason {
            self.census_dump(graph, &reason, true);
        } else if started.duration_since(self.census.last) >= CENSUS_INTERVAL {
            self.census_dump(graph, "periodic", false);
        }
    }

    pub(super) fn census_enter(&mut self, rule: RuleId) -> (RuleKey, Option<Instant>) {
        let found = &self.rules[rule.index()];
        let key = rule_key(found);
        self.census.applied.entry(key).or_insert_with(|| Applied {
            name: rule_name(found),
            ..Applied::default()
        });
        self.census.nesting += 1;
        let start = (self.census.nesting == 1).then(Instant::now);
        (key, start)
    }

    pub(super) fn census_leave(&mut self, key: RuleKey, start: Option<Instant>, objects: usize) {
        self.census.nesting -= 1;
        let applied = self.census.applied.get_mut(&key).expect("an entered rule");
        applied.calls += 1;
        applied.objects += objects as u64;
        applied.max_objects = applied.max_objects.max(objects as u64);
        if let Some(start) = start {
            applied.nanos += start.elapsed().as_nanos();
        }
    }

    pub(super) fn census_wake(&mut self, rule: &WaitingRule, receivers: usize, start: Instant) {
        let woken = self.census.woken.entry(waiting_name(rule)).or_default();
        woken.calls += 1;
        woken.objects += receivers as u64;
        woken.max_objects = woken.max_objects.max(receivers as u64);
        woken.nanos += start.elapsed().as_nanos();
    }

    pub(super) fn census_dump(&mut self, graph: &Graph, reason: &str, full: bool) {
        let started = Instant::now();
        let rss = rss_kib();
        let unix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("a clock after 1970")
            .as_secs_f64();
        let elapsed = started.duration_since(self.census.start).as_secs_f64();
        let prefix = format!(
            "CENSUS t={unix:.1} elapsed={elapsed:.1}s rss={}MiB {reason}",
            rss / KIB_PER_MIB
        );
        self.census_tables(graph, &prefix, full);
        self.census.dumps += 1;
        self.census.dump_nanos += started.elapsed().as_nanos();
        self.census.last = Instant::now();
        eprintln!(
            "{prefix} OVERHEAD steps={} checks={} check_ms={} dumps={} dump_ms={} this_dump_ms={}",
            self.census.steps,
            self.census.checks,
            self.census.check_nanos / 1_000_000,
            self.census.dumps,
            self.census.dump_nanos / 1_000_000,
            started.elapsed().as_millis()
        );
    }

    fn census_tables(&self, graph: &Graph, prefix: &str, full: bool) {
        let chains = &self.chains;
        let mut depth = vec![0u32; chains.links.len() + 1];
        for (index, &(parent, _)) in chains.links.iter().enumerate() {
            depth[index + 1] = depth[parent.0 as usize] + 1;
        }
        let mut accessors = Held::new();
        let mut accessor_sets = Sets::new();
        let mut methods = 0usize;
        for found in &self.accessors {
            accessors.add(found.receivers, &depth);
            methods += found.methods.len();
            if full {
                accessor_sets.add(chains.objects(found.receivers));
            }
        }
        let mut hooks = Held::new();
        let mut hook_sets = Sets::new();
        let (mut callers, mut results_of) = (0usize, 0usize);
        for found in &self.accessor_hooks {
            callers += found.callers.len();
            results_of += found.results_of.len();
            for &chain in found.receivers.values() {
                hooks.add(chain, &depth);
                if full {
                    hook_sets.add(chains.objects(chain));
                }
            }
        }
        let mut waiting = Held::new();
        let mut waiting_sets = Sets::new();
        for &chain in self.waiting.values() {
            waiting.add(chain, &depth);
            if full {
                waiting_sets.add(chains.objects(chain));
            }
        }
        let all_distinct: FxHashSet<Chain> = accessors
            .distinct_chains
            .iter()
            .chain(&hooks.distinct_chains)
            .chain(&waiting.distinct_chains)
            .copied()
            .collect();
        let held_links = {
            let mut used = vec![false; chains.links.len() + 1];
            for &chain in &all_distinct {
                let mut at = chain;
                while at != Chain::EMPTY && !used[at.0 as usize] {
                    used[at.0 as usize] = true;
                    at = chains.links[at.0 as usize - 1].0;
                }
            }
            used.iter().filter(|&&used| used).count()
        };
        eprintln!(
            "{prefix} CHAINS links={} links_cap={} extensions={} extensions_cap={} links_reachable_from_holders={} distinct_held_chains={} max_depth={} est_bytes(links={} extensions={})",
            chains.links.len(),
            chains.links.capacity(),
            chains.extensions.len(),
            chains.extensions.capacity(),
            held_links,
            all_distinct.len(),
            depth.iter().max().copied().unwrap_or(0),
            chains.links.capacity() * size_of::<(Chain, ObjId)>(),
            map_bytes::<(Chain, ObjId), Chain>(chains.extensions.capacity()),
        );
        eprintln!(
            "{prefix} ACC accessors={} {} methods={methods} by_key={}{}",
            self.accessors.len(),
            accessors.line(),
            self.accessor_receivers.len(),
            if full {
                format!(" {}", accessor_sets.line())
            } else {
                String::new()
            }
        );
        eprintln!(
            "{prefix} HOOKS records={} {} callers={callers} results_of={results_of} by_key={} rules={}{}",
            self.accessor_hooks.len(),
            hooks.line(),
            self.accessor_hooks_by_key.len(),
            self.accessor_hook_rules.len(),
            if full {
                format!(" {}", hook_sets.line())
            } else {
                String::new()
            }
        );
        eprintln!(
            "{prefix} WAITING {} watches_with_entries={} waiting_rules={} watches={} watch_of_witness={}{}",
            waiting.line(),
            self.waiting_order.len(),
            self.waiting_rules.len(),
            self.watches.len(),
            self.watch_of_witness.len(),
            if full {
                format!(" {}", waiting_sets.line())
            } else {
                String::new()
            }
        );
        self.census_rules(prefix);
        self.census_lookups(prefix);
        self.census_objects(prefix);
        self.census_calls(prefix);
        let mut applied: Vec<&Applied> = self
            .census
            .applied
            .values()
            .filter(|applied| applied.calls > 0)
            .collect();
        applied.sort_by(|a, b| b.nanos.cmp(&a.nanos).then(b.calls.cmp(&a.calls)));
        for found in applied {
            eprintln!(
                "{prefix} APPLIED {:<40} calls={} objects={} max_objects={} ms={}",
                found.name,
                found.calls,
                found.objects,
                found.max_objects,
                found.nanos / 1_000_000
            );
        }
        let mut woken: Vec<(&&str, &Applied)> = self.census.woken.iter().collect();
        woken.sort_by_key(|a| std::cmp::Reverse(a.1.nanos));
        for (name, found) in woken {
            eprintln!(
                "{prefix} WOKEN {name:<20} groups={} receivers={} max_receivers={} ms={}",
                found.calls,
                found.objects,
                found.max_objects,
                found.nanos / 1_000_000
            );
        }
        eprintln!(
            "{prefix} COUNTS add_object={} add_edge={} call_bound={} call_function={} accessors_apply_receiver={} accessors_add_method={}",
            self.census.add_object,
            self.census.add_edge,
            self.census.call_bound,
            self.census.call_function,
            self.census.accessors_apply_receiver,
            self.census.accessors_add_method
        );
        let mut tables = self.table_sizes();
        tables.sort_by_key(|a| std::cmp::Reverse(a.1));
        tables.truncate(30);
        eprintln!("{prefix} TABLES {tables:?}");
        graph.census(prefix);
    }

    fn census_rules(&self, prefix: &str) {
        let released: FxHashSet<usize> = self
            .released_rules
            .iter()
            .map(|rule| rule.index())
            .collect();
        let mut kinds: FxHashMap<RuleKey, (usize, usize)> = FxHashMap::default();
        let mut names: FxHashMap<RuleKey, String> = FxHashMap::default();
        let mut type_methods: FxHashMap<(crate::engine::CallId, ObjId), usize> =
            FxHashMap::default();
        let mut type_method_rules = 0usize;
        for (index, rule) in self.rules.iter().enumerate() {
            if released.contains(&index) {
                continue;
            }
            let key = rule_key(rule);
            let entry = kinds.entry(key).or_insert((0, index));
            entry.0 += 1;
            if let Rule::TypeMethod {
                object, implicit, ..
            } = rule
            {
                type_method_rules += 1;
                let class = match self.objects.get(*object) {
                    Object::Instance { class, .. } => *class,
                    _ => *object,
                };
                *type_methods.entry((*implicit, class)).or_default() += 1;
            }
        }
        for (key, &(_, index)) in &kinds {
            names.insert(*key, rule_name(&self.rules[index]));
        }
        let mut sorted: Vec<(String, usize)> = kinds
            .iter()
            .map(|(key, &(count, _))| (names[key].clone(), count))
            .collect();
        sorted.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        sorted.truncate(25);
        eprintln!(
            "{prefix} RULES slots={} slots_cap={} released={} live={} released_total={} reused_total={} est_bytes={} top={sorted:?}",
            self.rules.len(),
            self.rules.capacity(),
            self.released_rules.len(),
            self.rules.len() - released.len(),
            self.census.rules_released,
            self.census.rules_reused,
            self.rules.capacity() * size_of::<Rule>()
        );
        eprintln!(
            "{prefix} TYPEMETHOD rules={type_method_rules} groups_by_call_and_class={}",
            type_methods.len()
        );
        let binds_entries: usize = self.binds.iter().map(|b| b.receivers.len()).sum();
        let binds_instance: usize = self
            .binds
            .iter()
            .flat_map(|b| b.receivers.values())
            .filter(|r| r.is_some_and(|r| self.objects.get(r).kind() == Kind::Instance))
            .count();
        let shared_items: usize = self.shared.iter().map(|s| s.items.len()).sum();
        eprintln!(
            "{prefix} BINDS records={} receiver_entries={binds_entries} instance_receivers={binds_instance} field_binds={} fallback_binds={} metaclass_members={} shared={} shared_items={shared_items} shared_by_key={}",
            self.binds.len(),
            self.field_binds.len(),
            self.fallback_binds.len(),
            self.metaclass_members.len(),
            self.shared.len(),
            self.shared_by_key.len()
        );
    }

    fn census_lookups(&self, prefix: &str) {
        let (mut lookups, mut instance, mut class, mut other, mut none) = (0, 0, 0, 0, 0);
        let mut by_class_max = 0usize;
        for &c in &self.classes {
            let found = self.objects.class(c);
            by_class_max = by_class_max.max(found.lookups.len());
            for key in found.lookups.keys() {
                lookups += 1;
                match key.receiver.map(|r| self.objects.get(r).kind()) {
                    None => none += 1,
                    Some(Kind::Instance) => instance += 1,
                    Some(Kind::Class) => class += 1,
                    Some(_) => other += 1,
                }
            }
        }
        eprintln!(
            "{prefix} LOOKUPS classes={} lookups={lookups} with_instance_receiver={instance} with_class_receiver={class} with_other_receiver={other} without_receiver={none} max_per_class={by_class_max}",
            self.classes.len()
        );
    }

    fn census_objects(&self, prefix: &str) {
        let mut kinds: FxHashMap<&'static str, usize> = FxHashMap::default();
        for object in &self.objects.objects {
            *kinds.entry(object.kind().name()).or_default() += 1;
        }
        let mut kinds: Vec<(&str, usize)> = kinds.into_iter().collect();
        kinds.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));
        let class_instances: usize = self.class_instances.values().map(|s| s.len()).sum();
        eprintln!(
            "{prefix} OBJECTS total={} bound_methods={} instances={} class_instances={class_instances} supers={} by_kind={kinds:?}",
            self.objects.objects.len(),
            self.bound_methods.len(),
            self.instances.len(),
            self.supers.len()
        );
    }

    fn census_calls(&self, prefix: &str) {
        let (mut field_entries, mut instance_objects, mut instance_fields) = (0usize, 0usize, 0);
        for (&object, fields) in &self.fields {
            field_entries += fields.len();
            if self.objects.get(object).kind() == Kind::Instance {
                instance_objects += 1;
                instance_fields += fields.len();
            }
        }
        let reader_entries: usize = self
            .field_readers
            .values()
            .flat_map(|readers| readers.values())
            .map(|receivers| receivers.len())
            .sum();
        let group_receivers: usize = self.bound_groups.values().map(|g| g.len()).sum();
        eprintln!(
            "{prefix} CALLS calls={} calls_cap={} receiver_calls={} prefixes={} bound_groups={} bound_group_entries={group_receivers} group_records={} groups={} dunder_calls={} site_calls={} roots={} labels={} constants={} est_bytes(calls={} receiver_calls={})",
            self.calls.len(),
            self.calls.capacity(),
            self.receiver_calls.len(),
            self.prefixes.len(),
            self.bound_groups.len(),
            self.group_records.len(),
            self.groups.len(),
            self.dunder_calls.len(),
            self.site_calls.len(),
            self.roots.len(),
            self.labels.len(),
            self.constants.len(),
            self.calls.capacity() * size_of::<crate::engine::semantics::Call>(),
            map_bytes::<
                (crate::engine::CallId, crate::engine::semantics::Receivers),
                crate::engine::CallId,
            >(self.receiver_calls.capacity()),
        );
        eprintln!(
            "{prefix} FIELDS objects_with_fields={} field_entries={field_entries} instance_objects={instance_objects} instance_fields={instance_fields} field_readers={} reader_receivers={reader_entries} accesses={} receivers={} entry_receivers={}",
            self.fields.len(),
            self.field_readers.len(),
            self.accesses.len(),
            self.receivers.len(),
            self.entry_receivers.len()
        );
    }
}
