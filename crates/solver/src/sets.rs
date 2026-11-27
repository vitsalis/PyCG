use std::hash::Hasher;

use rustc_hash::{FxHashMap, FxHasher};

use crate::ids::{ObjId, SetId};

pub const SWEEP_NEW_OBJECTS_MIN: u64 = 1 << 20;

pub const KIND_SELECTION_OBJECTS_MIN: usize = 32;

pub type KindMask = u64;

#[derive(Clone, Copy)]
struct Span {
    start: u32,
    len: u32,
}

pub struct Sets {
    elements: Vec<u32>,
    spans: Vec<Span>,
    by_content: FxHashMap<u64, Vec<SetId>>,
    singletons: Vec<Option<SetId>>,
    union_by_ids: FxHashMap<(SetId, SetId), SetId>,
    difference_by_ids: FxHashMap<(SetId, SetId), SetId>,
    selection_by_id_and_kinds: FxHashMap<(SetId, KindMask), Vec<ObjId>>,
    number_by_object: Vec<Option<u32>>,
    object_by_number: Vec<ObjId>,
    kinds_by_number: Vec<KindMask>,
    pub copied: u64,
    pub new_sets_object_count: u64,
    pub sweep_at_new_objects: u64,
}

impl Default for Sets {
    fn default() -> Self {
        Self::new()
    }
}

impl Sets {
    pub fn new() -> Self {
        let mut sets = Sets {
            elements: Vec::new(),
            spans: Vec::new(),
            by_content: FxHashMap::default(),
            singletons: Vec::new(),
            union_by_ids: FxHashMap::default(),
            difference_by_ids: FxHashMap::default(),
            selection_by_id_and_kinds: FxHashMap::default(),
            number_by_object: Vec::new(),
            object_by_number: Vec::new(),
            kinds_by_number: Vec::new(),
            copied: 0,
            new_sets_object_count: 0,
            sweep_at_new_objects: SWEEP_NEW_OBJECTS_MIN,
        };
        let empty = sets.push(&[]);
        assert_eq!(empty, SetId::EMPTY);
        sets.by_content.insert(content_hash(&[]), vec![empty]);
        sets
    }

    pub fn number(&mut self, object: ObjId, kinds: KindMask) -> u32 {
        let index = object.index();
        if index >= self.number_by_object.len() {
            self.number_by_object.resize(index + 1, None);
        }
        if let Some(number) = self.number_by_object[index] {
            return number;
        }
        let number = u32::try_from(self.object_by_number.len()).expect("objects fit u32");
        self.number_by_object[index] = Some(number);
        self.object_by_number.push(object);
        self.kinds_by_number.push(kinds);
        number
    }

    pub fn number_of(&self, object: ObjId) -> Option<u32> {
        self.number_by_object.get(object.index()).copied().flatten()
    }

    pub fn object(&self, number: u32) -> ObjId {
        self.object_by_number[number as usize]
    }

    pub fn objects_numbered(&self) -> usize {
        self.object_by_number.len()
    }

    pub fn numbers(&self, set: SetId) -> &[u32] {
        let span = self.spans[set.index()];
        &self.elements[span.start as usize..(span.start + span.len) as usize]
    }

    pub fn len(&self, set: SetId) -> usize {
        self.spans[set.index()].len as usize
    }

    pub fn is_empty(&self, set: SetId) -> bool {
        self.len(set) == 0
    }

    pub fn contains(&self, set: SetId, number: u32) -> bool {
        self.numbers(set).binary_search(&number).is_ok()
    }

    pub fn ordered(&self, set: SetId) -> impl Iterator<Item = ObjId> + '_ {
        self.numbers(set).iter().map(|&number| self.object(number))
    }

    pub fn singleton(&mut self, object: ObjId, kinds: KindMask) -> SetId {
        let number = self.number(object, kinds);
        self.copied += 1;
        if let Some(Some(set)) = self.singletons.get(number as usize)
            && self.is_live(*set)
        {
            return *set;
        }
        let set = self.intern(&[number]);
        let index = number as usize;
        if index >= self.singletons.len() {
            self.singletons.resize(index + 1, None);
        }
        self.singletons[index] = Some(set);
        set
    }

    pub fn intern(&mut self, numbers: &[u32]) -> SetId {
        assert!(numbers.windows(2).all(|pair| pair[0] < pair[1]));
        let hash = content_hash(numbers);
        if let Some(found) = self.by_content.get(&hash) {
            for &set in found {
                if self.numbers(set) == numbers {
                    return set;
                }
            }
        }
        let set = self.push(numbers);
        self.by_content.entry(hash).or_default().push(set);
        self.new_sets_object_count += numbers.len() as u64;
        set
    }

    pub fn intern_unsorted(&mut self, mut numbers: Vec<u32>) -> SetId {
        numbers.sort_unstable();
        numbers.dedup();
        self.intern(&numbers)
    }

    pub fn union(&mut self, a: SetId, b: SetId) -> SetId {
        if self.is_empty(a) || a == b {
            return b;
        }
        if self.is_empty(b) {
            return a;
        }
        if let Some(&found) = self.union_by_ids.get(&(a, b)) {
            return found;
        }
        let merged = merge(self.numbers(a), self.numbers(b));
        self.copied += merged.len() as u64;
        let union = self.intern(&merged);
        self.union_by_ids.insert((a, b), union);
        union
    }

    pub fn union_all(&mut self, sets: &[SetId]) -> Vec<u32> {
        let mut numbers: Vec<u32> = sets
            .iter()
            .flat_map(|&set| self.numbers(set).iter().copied())
            .collect();
        numbers.sort_unstable();
        numbers.dedup();
        numbers
    }

    pub fn difference(&mut self, a: SetId, b: SetId) -> SetId {
        if self.is_empty(b) {
            return a;
        }
        if let Some(&found) = self.difference_by_ids.get(&(a, b)) {
            return found;
        }
        let right = self.numbers(b);
        let remaining: Vec<u32> = self
            .numbers(a)
            .iter()
            .copied()
            .filter(|number| right.binary_search(number).is_err())
            .collect();
        self.copied += remaining.len() as u64;
        let difference = self.intern(&remaining);
        self.difference_by_ids.insert((a, b), difference);
        difference
    }

    pub fn of_kinds(&mut self, set: SetId, kinds: KindMask) -> &[ObjId] {
        if !self.selection_by_id_and_kinds.contains_key(&(set, kinds)) {
            let selected: Vec<ObjId> = self
                .numbers(set)
                .iter()
                .filter(|&&number| self.kinds_by_number[number as usize] & kinds != 0)
                .map(|&number| self.object(number))
                .collect();
            self.selection_by_id_and_kinds
                .insert((set, kinds), selected);
        }
        &self.selection_by_id_and_kinds[&(set, kinds)]
    }

    pub fn kinds(&self, number: u32) -> KindMask {
        self.kinds_by_number[number as usize]
    }

    pub fn sweep(&mut self, live: impl IntoIterator<Item = SetId>) {
        let mut by_content: FxHashMap<u64, Vec<SetId>> = FxHashMap::default();
        by_content.insert(content_hash(&[]), vec![SetId::EMPTY]);
        let mut kept_objects: u64 = 0;
        for set in live {
            let numbers = self.numbers(set);
            let bucket = by_content.entry(content_hash(numbers)).or_default();
            if bucket.iter().any(|&kept| self.numbers(kept) == numbers) {
                continue;
            }
            bucket.push(set);
            kept_objects += numbers.len() as u64;
        }
        self.by_content = by_content;
        self.union_by_ids.clear();
        self.difference_by_ids.clear();
        self.selection_by_id_and_kinds.clear();
        self.new_sets_object_count = 0;
        self.sweep_at_new_objects = kept_objects.max(SWEEP_NEW_OBJECTS_MIN);
    }

    pub fn count(&self) -> usize {
        self.spans.len()
    }

    pub fn compact(&mut self, held: &[bool]) {
        assert_eq!(held.len(), self.spans.len(), "a flag per set");
        let mut kept = 0usize;
        for (span, &keep) in self.spans.iter_mut().zip(held) {
            if !keep {
                *span = Span { start: 0, len: 0 };
                continue;
            }
            let start = span.start as usize;
            let len = span.len as usize;
            assert!(kept <= start, "sets are stored in the order they are made");
            self.elements.copy_within(start..start + len, kept);
            span.start = u32::try_from(kept).expect("set elements fit u32");
            kept += len;
        }
        self.elements.truncate(kept);
        self.elements.shrink_to_fit();
    }

    pub fn sweep_due(&self) -> bool {
        self.new_sets_object_count > self.sweep_at_new_objects
    }

    fn is_live(&self, set: SetId) -> bool {
        let numbers = self.numbers(set);
        self.by_content
            .get(&content_hash(numbers))
            .is_some_and(|bucket| bucket.contains(&set))
    }

    fn push(&mut self, numbers: &[u32]) -> SetId {
        let start = u32::try_from(self.elements.len()).expect("set elements fit u32");
        let len = u32::try_from(numbers.len()).expect("a set fits u32");
        self.elements.extend_from_slice(numbers);
        let set = SetId::new(self.spans.len());
        self.spans.push(Span { start, len });
        set
    }
}

fn content_hash(numbers: &[u32]) -> u64 {
    let mut hasher = FxHasher::default();
    hasher.write_usize(numbers.len());
    for &number in numbers {
        hasher.write_u32(number);
    }
    hasher.finish()
}

fn merge(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut merged = Vec::with_capacity(a.len() + b.len());
    let (mut left, mut right) = (0, 0);
    while left < a.len() && right < b.len() {
        match a[left].cmp(&b[right]) {
            std::cmp::Ordering::Less => {
                merged.push(a[left]);
                left += 1;
            }
            std::cmp::Ordering::Greater => {
                merged.push(b[right]);
                right += 1;
            }
            std::cmp::Ordering::Equal => {
                merged.push(a[left]);
                left += 1;
                right += 1;
            }
        }
    }
    merged.extend_from_slice(&a[left..]);
    merged.extend_from_slice(&b[right..]);
    merged
}
