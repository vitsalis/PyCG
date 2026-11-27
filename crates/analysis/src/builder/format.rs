const OPEN: u32 = '{' as u32;
const CLOSE: u32 = '}' as u32;
const COLON: u32 = ':' as u32;
const BANG: u32 = '!' as u32;
const OPEN_BRACKET: u32 = '[' as u32;
const CLOSE_BRACKET: u32 = ']' as u32;
const DOT: u32 = '.' as u32;
const ZERO: u32 = '0' as u32;
const NINE: u32 = '9' as u32;
const INDEX_DIGITS_MAX: usize = 19;

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) enum FieldName {
    Index(Option<usize>),
    Name(Vec<u32>),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Field {
    pub first: FieldName,
    pub attributes: Option<Vec<Vec<u32>>>,
    pub conversion: Option<u32>,
    pub spec: Vec<u32>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct Markup {
    name: Vec<u32>,
    spec: Vec<u32>,
    conversion: Option<u32>,
}

pub(crate) struct Item {
    pub literal: Vec<u32>,
    markup: Option<Markup>,
}

impl Item {
    pub(crate) fn has_field(&self) -> bool {
        self.markup.is_some()
    }
}

pub(crate) fn parse(text: &[u32]) -> Option<Vec<Item>> {
    let mut found = Vec::new();
    let mut position = 0;
    while position < text.len() {
        let start = position;
        let mut character = 0;
        let mut markup = false;
        while position < text.len() {
            character = text[position];
            position += 1;
            if character == OPEN || character == CLOSE {
                markup = true;
                break;
            }
        }
        let at_end = position >= text.len();
        let mut end = position;
        if character == CLOSE && (at_end || text[position] != CLOSE) {
            return None;
        }
        if at_end && character == OPEN {
            return None;
        }
        if !at_end {
            if text[position] == character {
                position += 1;
                markup = false;
            } else {
                end -= 1;
            }
        }
        let markup = if markup {
            Some(field(text, &mut position)?)
        } else {
            None
        };
        found.push(Item {
            literal: text[start..end].to_vec(),
            markup,
        });
    }
    Some(found)
}

fn field(text: &[u32], position: &mut usize) -> Option<Markup> {
    let start = *position;
    let mut character = 0;
    while *position < text.len() {
        character = text[*position];
        *position += 1;
        if character == OPEN {
            return None;
        }
        if character == OPEN_BRACKET {
            while *position < text.len() && text[*position] != CLOSE_BRACKET {
                *position += 1;
            }
            continue;
        }
        if character == CLOSE || character == COLON || character == BANG {
            break;
        }
    }
    let name = text[start..*position - 1].to_vec();
    if character != BANG && character != COLON {
        if character != CLOSE {
            return None;
        }
        return Some(Markup {
            name,
            spec: Vec::new(),
            conversion: None,
        });
    }
    let mut conversion = None;
    if character == BANG {
        if *position >= text.len() {
            return None;
        }
        conversion = Some(text[*position]);
        *position += 1;
        if *position < text.len() {
            let next = text[*position];
            *position += 1;
            if next == CLOSE {
                return Some(Markup {
                    name,
                    spec: Vec::new(),
                    conversion,
                });
            }
            if next != COLON {
                return None;
            }
        }
    }
    let spec_start = *position;
    let mut depth = 1;
    while *position < text.len() {
        let character = text[*position];
        *position += 1;
        if character == OPEN {
            depth += 1;
        } else if character == CLOSE {
            depth -= 1;
            if depth == 0 {
                return Some(Markup {
                    name,
                    spec: text[spec_start..*position - 1].to_vec(),
                    conversion,
                });
            }
        }
    }
    None
}

fn is_ascii_digits(text: &[u32]) -> bool {
    !text.is_empty() && text.iter().all(|&c| (ZERO..=NINE).contains(&c))
}

fn index(digits: &[u32]) -> Option<usize> {
    let start = digits
        .iter()
        .position(|&c| c != ZERO)
        .unwrap_or(digits.len() - 1);
    let digits = &digits[start..];
    if digits.len() > INDEX_DIGITS_MAX {
        return None;
    }
    let value = digits
        .iter()
        .fold(0u64, |value, &digit| value * 10 + u64::from(digit - ZERO));
    Some(usize::try_from(value).expect("a nineteen-digit index fits usize"))
}

pub(crate) fn format_fields(text: &[u32]) -> Vec<Field> {
    let Some(items) = parse(text) else {
        return Vec::new();
    };
    items
        .into_iter()
        .filter_map(|item| item.markup)
        .map(|markup| {
            let mut parts = markup.name.split(|&c| c == DOT);
            let first = parts.next().expect("a split has a first part").to_vec();
            let attributes = if markup.name.contains(&OPEN_BRACKET) {
                None
            } else {
                Some(parts.map(<[u32]>::to_vec).collect())
            };
            let first = if is_ascii_digits(&first) {
                FieldName::Index(index(&first))
            } else {
                FieldName::Name(first)
            };
            Field {
                first,
                attributes,
                conversion: markup.conversion,
                spec: markup.spec,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(value: &str) -> Vec<u32> {
        value.chars().map(u32::from).collect()
    }

    fn named(name: &str, attributes: &[&str], conversion: Option<char>, spec: &str) -> Field {
        Field {
            first: FieldName::Name(text(name)),
            attributes: Some(attributes.iter().map(|a| text(a)).collect()),
            conversion: conversion.map(u32::from),
            spec: text(spec),
        }
    }

    #[test]
    fn fields_are_read_as_string_formatter_parses_them() {
        assert_eq!(
            format_fields(&text("{a.b.c!r:>{w}} {{x}} {}")),
            vec![
                named("a", &["b", "c"], Some('r'), ">{w}"),
                named("", &[], None, ""),
            ]
        );
        let fields = format_fields(&text("{0012} {12345678901234567890} {x[0].y}"));
        assert_eq!(fields[0].first, FieldName::Index(Some(12)));
        assert_eq!(fields[1].first, FieldName::Index(None));
        assert_eq!(fields[2].attributes, None);
        assert_eq!(
            format_fields(&text("{000}"))[0].first,
            FieldName::Index(Some(0))
        );
    }

    #[test]
    fn a_malformed_format_has_no_fields() {
        for malformed in [
            "{", "}", "a}b", "{a", "{a!r", "{a!rx}", "{a:{b}", "{{a}", "{a{b}}", "{!", "{a!}",
            "{[}",
        ] {
            assert_eq!(format_fields(&text(malformed)), Vec::new(), "{malformed}");
        }
        assert_eq!(format_fields(&text("{{}}")), Vec::new());
        assert_eq!(
            format_fields(&text("{a!}}"))[0].conversion,
            Some(u32::from('}'))
        );
        assert_eq!(format_fields(&text("{a[}b]}"))[0].attributes, None);
        assert_eq!(
            format_fields(&text("{:}"))[0].first,
            FieldName::Name(Vec::new())
        );
    }
}
