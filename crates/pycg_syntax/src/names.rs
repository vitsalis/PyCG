use std::borrow::Cow;
use std::sync::OnceLock;

use rustc_hash::FxHashMap;

const DATA: &str = include_str!("../data/unicode.txt");

const HANGUL_SYLLABLE_BASE: u32 = 0xAC00;
const HANGUL_LEADING_BASE: u32 = 0x1100;
const HANGUL_VOWEL_BASE: u32 = 0x1161;
const HANGUL_TRAILING_BASE: u32 = 0x11A7;
const HANGUL_LEADING_COUNT: u32 = 19;
const HANGUL_VOWEL_COUNT: u32 = 21;
const HANGUL_TRAILING_COUNT: u32 = 28;
const HANGUL_SYLLABLES_PER_LEADING: u32 = HANGUL_VOWEL_COUNT * HANGUL_TRAILING_COUNT;
const HANGUL_SYLLABLE_COUNT: u32 = HANGUL_LEADING_COUNT * HANGUL_SYLLABLES_PER_LEADING;

struct Tables {
    decompositions: FxHashMap<char, Vec<char>>,
    combining: FxHashMap<char, u8>,
    compositions: FxHashMap<(char, char), char>,
    start: Vec<(u32, u32)>,
    continuing: Vec<(u32, u32)>,
}

fn tables() -> &'static Tables {
    static TABLES: OnceLock<Tables> = OnceLock::new();
    TABLES.get_or_init(|| parse_data(DATA))
}

fn code_point(word: &str) -> char {
    let point = u32::from_str_radix(word, 16).expect("a code point is hexadecimal");
    char::from_u32(point).expect("a listed code point is a character")
}

fn parse_ranges<'w>(words: impl Iterator<Item = &'w str>) -> Vec<(u32, u32)> {
    words
        .map(|word| {
            let (low, high) = word.split_once('-').expect("a range has two ends");
            let bound = |end: &str| u32::from_str_radix(end, 16).expect("hexadecimal");
            (bound(low), bound(high))
        })
        .collect()
}

fn parse_data(data: &str) -> Tables {
    let mut tables = Tables {
        decompositions: FxHashMap::default(),
        combining: FxHashMap::default(),
        compositions: FxHashMap::default(),
        start: Vec::new(),
        continuing: Vec::new(),
    };
    for line in data.lines() {
        let mut words = line.split(' ');
        match words.next() {
            Some("unicode") => {}
            Some("decompose") => {
                let point = code_point(words.next().expect("a decomposed code point"));
                tables
                    .decompositions
                    .insert(point, words.map(code_point).collect());
            }
            Some("combining") => {
                let point = code_point(words.next().expect("a combining code point"));
                let class = words.next().expect("a combining class");
                tables
                    .combining
                    .insert(point, class.parse().expect("a class is a number"));
            }
            Some("compose") => {
                let parts: Vec<char> = words.map(code_point).collect();
                let [first, second, composite] = parts[..] else {
                    panic!("composition {line:?}");
                };
                tables.compositions.insert((first, second), composite);
            }
            Some("start") => tables.start = parse_ranges(words),
            Some("continue") => tables.continuing = parse_ranges(words),
            _ => panic!("unicode data line {line:?}"),
        }
    }
    tables
}

pub fn identifier(text: &str) -> Cow<'_, str> {
    if text.is_ascii() {
        return Cow::Borrowed(text);
    }
    Cow::Owned(nfkc(text))
}

pub fn nfkc(text: &str) -> String {
    let tables = tables();
    let mut decomposed = Vec::with_capacity(text.len());
    for character in text.chars() {
        decompose(tables, character, &mut decomposed);
    }
    reorder(tables, &mut decomposed);
    compose(tables, &decomposed).into_iter().collect()
}

fn decompose(tables: &Tables, character: char, found: &mut Vec<char>) {
    let point = u32::from(character);
    if (HANGUL_SYLLABLE_BASE..HANGUL_SYLLABLE_BASE + HANGUL_SYLLABLE_COUNT).contains(&point) {
        let index = point - HANGUL_SYLLABLE_BASE;
        let leading = HANGUL_LEADING_BASE + index / HANGUL_SYLLABLES_PER_LEADING;
        let vowel =
            HANGUL_VOWEL_BASE + (index % HANGUL_SYLLABLES_PER_LEADING) / HANGUL_TRAILING_COUNT;
        let trailing = index % HANGUL_TRAILING_COUNT;
        found.push(hangul(leading));
        found.push(hangul(vowel));
        if trailing != 0 {
            found.push(hangul(HANGUL_TRAILING_BASE + trailing));
        }
        return;
    }
    match tables.decompositions.get(&character) {
        Some(parts) => found.extend(parts.iter().copied()),
        None => found.push(character),
    }
}

fn hangul(point: u32) -> char {
    char::from_u32(point).expect("a Hangul jamo is a character")
}

fn combining(tables: &Tables, character: char) -> u8 {
    tables.combining.get(&character).copied().unwrap_or(0)
}

fn reorder(tables: &Tables, characters: &mut [char]) {
    let mut start = 0;
    while start < characters.len() {
        if combining(tables, characters[start]) == 0 {
            start += 1;
            continue;
        }
        let end = start
            + characters[start..]
                .iter()
                .take_while(|&&c| combining(tables, c) != 0)
                .count();
        characters[start..end].sort_by_key(|&c| combining(tables, c));
        start = end;
    }
}

fn compose_pair(tables: &Tables, first: char, second: char) -> Option<char> {
    let (a, b) = (u32::from(first), u32::from(second));
    let leading = HANGUL_LEADING_BASE..HANGUL_LEADING_BASE + HANGUL_LEADING_COUNT;
    let vowel = HANGUL_VOWEL_BASE..HANGUL_VOWEL_BASE + HANGUL_VOWEL_COUNT;
    if leading.contains(&a) && vowel.contains(&b) {
        let index = (a - HANGUL_LEADING_BASE) * HANGUL_SYLLABLES_PER_LEADING
            + (b - HANGUL_VOWEL_BASE) * HANGUL_TRAILING_COUNT;
        return Some(hangul(HANGUL_SYLLABLE_BASE + index));
    }
    let syllables = HANGUL_SYLLABLE_BASE..HANGUL_SYLLABLE_BASE + HANGUL_SYLLABLE_COUNT;
    let trailing = HANGUL_TRAILING_BASE + 1..HANGUL_TRAILING_BASE + HANGUL_TRAILING_COUNT;
    if syllables.contains(&a)
        && (a - HANGUL_SYLLABLE_BASE).is_multiple_of(HANGUL_TRAILING_COUNT)
        && trailing.contains(&b)
    {
        return Some(hangul(a + b - HANGUL_TRAILING_BASE));
    }
    tables.compositions.get(&(first, second)).copied()
}

fn compose(tables: &Tables, characters: &[char]) -> Vec<char> {
    let mut found: Vec<char> = Vec::with_capacity(characters.len());
    let mut starter: Option<usize> = None;
    let mut last_class: Option<u8> = None;
    for &character in characters {
        let class = combining(tables, character);
        if let Some(index) = starter {
            let blocked = last_class.is_some_and(|last| last == 0 || last >= class);
            if !blocked && let Some(composite) = compose_pair(tables, found[index], character) {
                found[index] = composite;
                continue;
            }
        }
        if class == 0 {
            starter = Some(found.len());
            last_class = None;
        } else {
            last_class = Some(class);
        }
        found.push(character);
    }
    found
}

fn within(ranges: &[(u32, u32)], character: char) -> bool {
    let point = u32::from(character);
    let index = ranges.partition_point(|&(_, high)| high < point);
    ranges.get(index).is_some_and(|&(low, _)| low <= point)
}

pub fn is_python_space(character: char) -> bool {
    character.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&character)
}

pub fn is_identifier(text: &str) -> bool {
    let tables = tables();
    let mut characters = text.chars();
    let Some(first) = characters.next() else {
        return false;
    };
    within(&tables.start, first) && characters.all(|c| within(&tables.continuing, c))
}
