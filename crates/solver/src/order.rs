use std::collections::VecDeque;

const SPLITMIX_INCREMENT: u64 = 0x9E37_79B9_7F4A_7C15;
const SPLITMIX_FIRST_MULTIPLIER: u64 = 0xBF58_476D_1CE4_E5B9;
const SPLITMIX_SECOND_MULTIPLIER: u64 = 0x94D0_49BB_1331_11EB;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Order {
    Canonical,
    LastInFirstOut,
    Reversed,
    Shuffled { state: u64 },
}

impl Order {
    pub fn shuffled(seed: u64) -> Order {
        Order::Shuffled { state: seed }
    }

    pub fn take<T>(&mut self, worklist: &mut VecDeque<T>) -> Option<T> {
        match self {
            Order::Canonical | Order::Reversed => worklist.pop_front(),
            Order::LastInFirstOut => worklist.pop_back(),
            Order::Shuffled { state } => {
                if worklist.is_empty() {
                    return None;
                }
                let turn = below(state, worklist.len());
                worklist.rotate_left(turn);
                worklist.pop_front()
            }
        }
    }

    pub fn arrange<T>(&mut self, items: &mut [T]) {
        match self {
            Order::Canonical | Order::LastInFirstOut => {}
            Order::Reversed => items.reverse(),
            Order::Shuffled { state } => {
                for last in (1..items.len()).rev() {
                    let other = below(state, last + 1);
                    items.swap(last, other);
                }
            }
        }
    }
}

fn below(state: &mut u64, bound: usize) -> usize {
    assert!(bound > 0);
    *state = state.wrapping_add(SPLITMIX_INCREMENT);
    let mut mixed = *state;
    mixed = (mixed ^ (mixed >> 30)).wrapping_mul(SPLITMIX_FIRST_MULTIPLIER);
    mixed = (mixed ^ (mixed >> 27)).wrapping_mul(SPLITMIX_SECOND_MULTIPLIER);
    mixed ^= mixed >> 31;
    let bound = u64::try_from(bound).expect("a bound fits in 64 bits");
    usize::try_from(mixed % bound).expect("an index below a usize bound")
}
