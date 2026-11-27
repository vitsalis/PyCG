use crate::unicode::{DECIMAL_ZEROS, NOT_PRINTABLE, SPACES_NOT_ASCII};

const DIGITS_PER_BLOCK: u32 = 10;
const ASCII_DELETE: char = '\u{7f}';
const LATIN_1_LAST: u32 = 0xff;
const BASIC_PLANE_LAST: u32 = 0xffff;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Unit {
    Char(char),
    Byte(u8),
}

pub fn units(bytes: &[u8]) -> impl Iterator<Item = Unit> + '_ {
    bytes.utf8_chunks().flat_map(|chunk| {
        let characters = chunk.valid().chars().map(Unit::Char);
        characters.chain(chunk.invalid().iter().map(|byte| Unit::Byte(*byte)))
    })
}

pub fn first_unit_length(bytes: &[u8]) -> usize {
    match units(bytes).next() {
        None => 0,
        Some(Unit::Char(character)) => character.len_utf8(),
        Some(Unit::Byte(_)) => 1,
    }
}

pub fn length(bytes: &[u8]) -> i64 {
    let count = units(bytes).count();
    i64::try_from(count).expect("a length that fits in i64")
}

pub fn decimal(character: char) -> Option<u32> {
    let point = u32::from(character);
    let index = DECIMAL_ZEROS.partition_point(|zero| *zero <= point);
    let zero = DECIMAL_ZEROS[index.checked_sub(1)?];
    let value = point - zero;
    (value < DIGITS_PER_BLOCK).then_some(value)
}

pub fn is_space_not_ascii(character: char) -> bool {
    SPACES_NOT_ASCII
        .binary_search(&u32::from(character))
        .is_ok()
}

fn is_printable(character: char) -> bool {
    let point = u32::from(character);
    let index = NOT_PRINTABLE.partition_point(|(first, _)| *first <= point);
    match index.checked_sub(1) {
        None => true,
        Some(index) => point > NOT_PRINTABLE[index].1,
    }
}

fn escaped(out: &mut String, point: u32) {
    if point <= LATIN_1_LAST {
        out.push_str(&format!("\\x{point:02x}"));
    } else if point <= BASIC_PLANE_LAST {
        out.push_str(&format!("\\u{point:04x}"));
    } else {
        out.push_str(&format!("\\U{point:08x}"));
    }
}

pub fn surrogate(byte: u8) -> u32 {
    0xdc00 + u32::from(byte)
}

pub fn repr(bytes: &[u8]) -> String {
    let single = units(bytes).any(|unit| unit == Unit::Char('\''));
    let double = units(bytes).any(|unit| unit == Unit::Char('"'));
    let quote = if single && !double { '"' } else { '\'' };
    let mut out = String::new();
    out.push(quote);
    for unit in units(bytes) {
        match unit {
            Unit::Byte(byte) => escaped(&mut out, surrogate(byte)),
            Unit::Char(character) if character == quote || character == '\\' => {
                out.push('\\');
                out.push(character);
            }
            Unit::Char('\t') => out.push_str("\\t"),
            Unit::Char('\n') => out.push_str("\\n"),
            Unit::Char('\r') => out.push_str("\\r"),
            Unit::Char(character) if character < ' ' || character == ASCII_DELETE => {
                escaped(&mut out, u32::from(character));
            }
            Unit::Char(character) if character.is_ascii() || is_printable(character) => {
                out.push(character);
            }
            Unit::Char(character) => escaped(&mut out, u32::from(character)),
        }
    }
    out.push(quote);
    out
}

pub fn for_stderr(bytes: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(bytes.len());
    for chunk in bytes.utf8_chunks() {
        out.extend_from_slice(chunk.valid().as_bytes());
        for byte in chunk.invalid() {
            out.extend_from_slice(format!("\\u{:04x}", surrogate(*byte)).as_bytes());
        }
    }
    out
}
