use std::fmt::Write as _;

use num_bigint::{BigInt, BigUint, Sign};

pub const BUILTIN_MODULE: &str = "<builtin>";
pub const SITE_SEPARATOR: char = '#';
pub const CONSTANT_NAME_DECIMAL_DIGITS_MAX: u32 = 640;

pub fn site_name(site: &str) -> &str {
    site.split_once(SITE_SEPARATOR)
        .map_or(site, |(name, _)| name)
}

pub fn steps_past_root(name: &str, steps: usize) -> Vec<&str> {
    if steps == 0 {
        return Vec::new();
    }
    let parts: Vec<&str> = name.split('.').collect();
    parts[parts.len().saturating_sub(steps)..].to_vec()
}

pub enum ConstValue<'a> {
    Str(&'a [u32]),
    Bytes(&'a [u8]),
    Int(&'a BigInt),
}

pub fn constant_name(value: &ConstValue<'_>) -> String {
    match value {
        ConstValue::Str(code_points) => ascii_str(code_points),
        ConstValue::Bytes(bytes) => ascii_bytes(bytes),
        ConstValue::Int(value) => int_name(value),
    }
}

pub fn constant_type_name(value: &ConstValue<'_>) -> &'static str {
    match value {
        ConstValue::Str(_) => "str",
        ConstValue::Bytes(_) => "bytes",
        ConstValue::Int(_) => "int",
    }
}

fn int_name(value: &BigInt) -> String {
    let limit = BigUint::from(10u32).pow(CONSTANT_NAME_DECIMAL_DIGITS_MAX);
    if *value.magnitude() < limit {
        return value.to_string();
    }
    let sign = if value.sign() == Sign::Minus { "-" } else { "" };
    format!("{sign}0x{}", value.magnitude().to_str_radix(16))
}

const SINGLE_QUOTE: u32 = '\'' as u32;
const DOUBLE_QUOTE: u32 = '"' as u32;
const BACKSLASH: u32 = '\\' as u32;
const TAB: u32 = '\t' as u32;
const NEWLINE: u32 = '\n' as u32;
const CARRIAGE_RETURN: u32 = '\r' as u32;
const PRINTABLE_FIRST: u32 = 0x20;
const PRINTABLE_LAST: u32 = 0x7e;
const BYTE_LIMIT: u32 = 0x100;
const BASIC_PLANE_LIMIT: u32 = 0x1_0000;

fn quote_for(has_single: bool, has_double: bool) -> char {
    if has_single && !has_double { '"' } else { '\'' }
}

pub fn ascii_str(code_points: &[u32]) -> String {
    let quote = quote_for(
        code_points.contains(&SINGLE_QUOTE),
        code_points.contains(&DOUBLE_QUOTE),
    );
    let mut out = String::with_capacity(code_points.len() + 2);
    out.push(quote);
    for &point in code_points {
        escape_point(&mut out, point, quote);
    }
    out.push(quote);
    out
}

fn escape_point(out: &mut String, point: u32, quote: char) {
    match point {
        BACKSLASH => out.push_str("\\\\"),
        TAB => out.push_str("\\t"),
        NEWLINE => out.push_str("\\n"),
        CARRIAGE_RETURN => out.push_str("\\r"),
        _ if point == quote as u32 => {
            out.push('\\');
            out.push(quote);
        }
        PRINTABLE_FIRST..=PRINTABLE_LAST => {
            out.push(char::from_u32(point).expect("an ASCII code point"));
        }
        _ if point < BYTE_LIMIT => write!(out, "\\x{point:02x}").expect("write"),
        _ if point < BASIC_PLANE_LIMIT => write!(out, "\\u{point:04x}").expect("write"),
        _ => write!(out, "\\U{point:08x}").expect("write"),
    }
}

pub fn ascii_bytes(bytes: &[u8]) -> String {
    let quote = quote_for(bytes.contains(&b'\''), bytes.contains(&b'"'));
    let mut out = String::with_capacity(bytes.len() + 3);
    out.push('b');
    out.push(quote);
    for &byte in bytes {
        match byte {
            b'\\' => out.push_str("\\\\"),
            b'\t' => out.push_str("\\t"),
            b'\n' => out.push_str("\\n"),
            b'\r' => out.push_str("\\r"),
            _ if byte == quote as u8 => {
                out.push('\\');
                out.push(quote);
            }
            0x20..=0x7e => out.push(char::from(byte)),
            _ => write!(out, "\\x{byte:02x}").expect("write"),
        }
    }
    out.push(quote);
    out
}

pub fn ascii_text(text: &str) -> String {
    let code_points: Vec<u32> = text.chars().map(u32::from).collect();
    ascii_str(&code_points)
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Signature {
    pub positional: Box<[Box<str>]>,
    pub positional_only_count: usize,
    pub keyword_only: Box<[Box<str>]>,
    pub vararg: Option<Box<str>>,
    pub kwarg: Option<Box<str>>,
}

impl Signature {
    pub fn new(
        positional: Vec<Box<str>>,
        positional_only_count: usize,
        keyword_only: Vec<Box<str>>,
        vararg: Option<Box<str>>,
        kwarg: Option<Box<str>>,
    ) -> Signature {
        assert!(positional_only_count <= positional.len());
        Signature {
            positional: positional.into_boxed_slice(),
            positional_only_count,
            keyword_only: keyword_only.into_boxed_slice(),
            vararg,
            kwarg,
        }
    }

    pub fn names(&self) -> Vec<&str> {
        self.positional
            .iter()
            .chain(self.keyword_only.iter())
            .chain(self.vararg.iter().filter(|name| !name.is_empty()))
            .chain(self.kwarg.iter().filter(|name| !name.is_empty()))
            .map(|name| &**name)
            .collect()
    }

    pub fn accepts_keyword(&self, name: &str) -> bool {
        self.positional[self.positional_only_count..]
            .iter()
            .chain(self.keyword_only.iter())
            .any(|parameter| &**parameter == name)
    }

    pub fn binds(&self, given: usize, keywords: &[&str], optional: &[&str]) -> bool {
        if given > self.positional.len() && self.vararg.is_none() {
            return false;
        }
        let mut filled: Vec<&str> = self.positional[..given.min(self.positional.len())]
            .iter()
            .map(|name| &**name)
            .collect();
        for &name in keywords {
            if self.accepts_keyword(name) {
                if filled.contains(&name) {
                    return false;
                }
                filled.push(name);
            } else if self.kwarg.is_none() {
                return false;
            }
        }
        self.positional
            .iter()
            .chain(self.keyword_only.iter())
            .filter(|name| !optional.contains(&&***name))
            .all(|name| filled.contains(&&**name))
    }
}

pub fn instance_name(class: &str, site: &str) -> String {
    format!("{class}@{}", site_name(site))
}

pub fn bound_method_name(function: &str, receiver: &str) -> String {
    format!("<bound {function} of {receiver}>")
}

pub fn fallback_name(method: &str) -> String {
    format!("<fallback {method}>")
}

pub fn wrapper_name(kind: &str, site: &str) -> String {
    format!("{kind}@{}", site_name(site))
}

pub fn container_name(kind: &str, site: &str) -> String {
    format!("{kind}@{}", site_name(site))
}

pub fn super_name(class: &str, receiver: &str) -> String {
    format!("super({class}, {receiver})")
}

pub fn generator_name(function: &str) -> String {
    format!("generator@{function}")
}

pub fn coroutine_name(function: &str) -> String {
    format!("coroutine@{function}")
}
