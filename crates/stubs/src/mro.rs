use std::collections::VecDeque;
use std::hash::Hash;

use rustc_hash::{FxHashMap, FxHashSet};

pub fn linearize<'m, T>(class: &T, bases: &[T], mro_of: impl Fn(&T) -> &'m [T]) -> Vec<T>
where
    T: Clone + Eq + Hash + 'm,
{
    let mut usable: Vec<T> = Vec::new();
    for base in bases {
        if base == class || usable.contains(base) || mro_of(base).contains(class) {
            continue;
        }
        usable.push(base.clone());
    }
    let base_mros: Vec<&[T]> = usable.iter().map(&mro_of).collect();
    let mut sequences: Vec<&[T]> = base_mros.clone();
    sequences.push(&usable);
    let merged = match c3_merge(&sequences) {
        Some(merged) => merged,
        None => first_occurrences(base_mros.iter().flat_map(|mro| mro.iter())),
    };
    let mut result = Vec::with_capacity(merged.len() + 1);
    result.push(class.clone());
    result.extend(merged);
    result
}

fn c3_merge<T: Clone + Eq + Hash>(sequences: &[&[T]]) -> Option<Vec<T>> {
    let mut sequences: Vec<VecDeque<&T>> = sequences
        .iter()
        .filter(|sequence| !sequence.is_empty())
        .map(|sequence| sequence.iter().collect())
        .collect();
    let mut tail_occurrences: FxHashMap<&T, i64> = FxHashMap::default();
    for sequence in &sequences {
        for item in sequence.iter().skip(1) {
            *tail_occurrences.entry(*item).or_insert(0) += 1;
        }
    }
    let mut result = Vec::new();
    while !sequences.is_empty() {
        let head: T = sequences
            .iter()
            .map(|sequence| sequence[0])
            .find(|head| tail_occurrences.get(head).copied().unwrap_or(0) == 0)?
            .clone();
        result.push(head.clone());
        for sequence in &mut sequences {
            if *sequence[0] == head {
                sequence.pop_front();
                if let Some(next) = sequence.front() {
                    *tail_occurrences.entry(*next).or_insert(0) -= 1;
                }
            }
        }
        sequences.retain(|sequence| !sequence.is_empty());
    }
    Some(result)
}

fn first_occurrences<'a, T: Clone + Eq + Hash + 'a>(items: impl Iterator<Item = &'a T>) -> Vec<T> {
    let mut seen: FxHashSet<&T> = FxHashSet::default();
    let mut result = Vec::new();
    for item in items {
        if seen.insert(item) {
            result.push(item.clone());
        }
    }
    result
}

pub fn linearizations<T>(
    class: &T,
    slots: &[Vec<Option<T>>],
    mros_of: impl Fn(Option<&T>) -> Vec<Vec<T>>,
    limit: u64,
) -> Option<Vec<Vec<T>>>
where
    T: Clone + Eq + Hash,
{
    let choices: Vec<Vec<(Option<&T>, Vec<T>)>> = slots
        .iter()
        .map(|slot| {
            slot.iter()
                .flat_map(|candidate| {
                    mros_of(candidate.as_ref())
                        .into_iter()
                        .map(move |mro| (candidate.as_ref(), mro))
                })
                .collect()
        })
        .collect();
    let combinations = choices.iter().fold(1u64, |product, choice| {
        product.saturating_mul(choice.len() as u64)
    });
    if combinations > limit {
        return None;
    }
    let mut result: Vec<Vec<T>> = Vec::new();
    if choices.iter().any(Vec::is_empty) {
        return Some(result);
    }
    let mut indices = vec![0usize; choices.len()];
    loop {
        let mut chosen: Vec<(&T, &[T])> = Vec::new();
        for (choice, &index) in choices.iter().zip(&indices) {
            let (candidate, mro) = &choice[index];
            if let Some(candidate) = candidate
                && !chosen.iter().any(|(seen, _)| seen == candidate)
            {
                chosen.push((candidate, mro));
            }
        }
        let bases: Vec<T> = chosen
            .iter()
            .map(|(candidate, _)| (*candidate).clone())
            .collect();
        let mro = linearize(class, &bases, |base| {
            chosen
                .iter()
                .find(|(candidate, _)| *candidate == base)
                .map(|(_, mro)| *mro)
                .expect("every base was chosen")
        });
        if !result.contains(&mro) {
            result.push(mro);
        }
        if !advance(&mut indices, &choices) {
            return Some(result);
        }
    }
}

fn advance<C>(indices: &mut [usize], choices: &[Vec<C>]) -> bool {
    for position in (0..indices.len()).rev() {
        indices[position] += 1;
        if indices[position] < choices[position].len() {
            return true;
        }
        indices[position] = 0;
    }
    false
}

pub fn exhaustive_order<T>(
    class: &T,
    slots: &[Vec<Option<T>>],
    mros_of: impl Fn(Option<&T>) -> Vec<Vec<T>>,
) -> Vec<T>
where
    T: Clone + Eq + Hash,
{
    let mros: Vec<Vec<T>> = slots
        .iter()
        .flatten()
        .filter_map(Option::as_ref)
        .filter(|candidate| *candidate != class)
        .flat_map(|candidate| mros_of(Some(candidate)))
        .collect();
    let mut result = vec![class.clone()];
    result.extend(first_occurrences(
        mros.iter().flatten().filter(|item| *item != class),
    ));
    result
}
