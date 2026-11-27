use std::cmp::Ordering;
use std::collections::BTreeMap;

use num_bigint::BigInt;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(BigInt),
    Str(Text),
    Array(Vec<Value>),
    Object(BTreeMap<String, Value>),
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Text(Repr);

#[derive(Clone, Debug, PartialEq, Eq)]
enum Repr {
    Unicode(String),
    WithSurrogates(Box<[u32]>),
}

impl Text {
    pub fn from_code_points(points: &[u32]) -> Text {
        match points.iter().map(|&point| char::from_u32(point)).collect() {
            Some(text) => Text(Repr::Unicode(text)),
            None => {
                assert!(
                    points.iter().all(|&point| point <= u32::from(char::MAX)),
                    "a code point of a str is at most U+10FFFF"
                );
                Text(Repr::WithSurrogates(points.into()))
            }
        }
    }

    fn code_points(&self) -> Box<dyn Iterator<Item = u32> + '_> {
        match &self.0 {
            Repr::Unicode(text) => Box::new(text.chars().map(u32::from)),
            Repr::WithSurrogates(points) => Box::new(points.iter().copied()),
        }
    }
}

impl From<String> for Text {
    fn from(text: String) -> Text {
        Text(Repr::Unicode(text))
    }
}

impl From<&str> for Text {
    fn from(text: &str) -> Text {
        Text(Repr::Unicode(text.to_owned()))
    }
}

impl Ord for Text {
    fn cmp(&self, other: &Text) -> Ordering {
        self.code_points().cmp(other.code_points())
    }
}

impl PartialOrd for Text {
    fn partial_cmp(&self, other: &Text) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

pub fn dumps(value: &Value) -> String {
    let mut out = String::new();
    write_value(&mut out, value);
    out
}

fn write_value(out: &mut String, value: &Value) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Int(number) => out.push_str(&number.to_string()),
        Value::Str(text) => write_str(out, text.code_points()),
        Value::Array(items) => {
            out.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_value(out, item);
            }
            out.push(']');
        }
        Value::Object(fields) => {
            out.push('{');
            for (index, (key, field)) in fields.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                write_str(out, key.chars().map(u32::from));
                out.push(':');
                write_value(out, field);
            }
            out.push('}');
        }
    }
}

fn write_str(out: &mut String, points: impl Iterator<Item = u32>) {
    out.push('"');
    for point in points {
        match char::from_u32(point) {
            Some('"') => out.push_str("\\\""),
            Some('\\') => out.push_str("\\\\"),
            Some('\n') => out.push_str("\\n"),
            Some('\r') => out.push_str("\\r"),
            Some('\t') => out.push_str("\\t"),
            Some('\u{8}') => out.push_str("\\b"),
            Some('\u{c}') => out.push_str("\\f"),
            Some(character @ ' '..='~') => out.push(character),
            Some(character) => {
                let mut units = [0u16; 2];
                for unit in character.encode_utf16(&mut units) {
                    out.push_str(&format!("\\u{unit:04x}"));
                }
            }
            None => out.push_str(&format!("\\u{point:04x}")),
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::{Text, Value, dumps};
    use num_bigint::BigInt;
    use std::collections::BTreeMap;

    fn text(value: &str) -> String {
        dumps(&Value::Str(value.into()))
    }

    #[test]
    fn control_characters_use_the_short_escapes_or_four_hex_digits() {
        assert_eq!(
            text("a\n\r\t\u{8}\u{c}\u{0}\u{1f}\u{7f}"),
            r#""a\n\r\t\b\f\u0000\u001f\u007f""#
        );
    }

    #[test]
    fn quotes_and_backslashes_are_escaped_and_slashes_are_not() {
        assert_eq!(text("q\"b\\s/"), r#""q\"b\\s/""#);
    }

    #[test]
    fn printable_ascii_is_written_as_is() {
        assert_eq!(text(" ~"), r#"" ~""#);
    }

    #[test]
    fn characters_past_ascii_are_escaped_in_lower_case_hex() {
        assert_eq!(text("\u{e9}\u{20ac}"), "\"\\u00e9\\u20ac\"");
    }

    #[test]
    fn characters_past_the_basic_plane_are_escaped_as_surrogate_pairs() {
        assert_eq!(text("\u{1F600}"), "\"\\ud83d\\ude00\"");
    }

    #[test]
    fn a_lone_surrogate_is_escaped_as_itself() {
        let points = [u32::from('a'), 0xdc80, 0xd83d];

        assert_eq!(
            dumps(&Value::Str(Text::from_code_points(&points))),
            "\"a\\udc80\\ud83d\""
        );
    }

    #[test]
    fn code_points_without_a_surrogate_are_the_same_text_as_a_string() {
        let points: Vec<u32> = "ab\u{e9}".chars().map(u32::from).collect();

        assert_eq!(Text::from_code_points(&points), Text::from("ab\u{e9}"));
    }

    #[test]
    fn texts_are_ordered_by_code_point() {
        let surrogate = Text::from_code_points(&[0xd800]);

        assert!(Text::from("\u{ffff}") > surrogate);
        assert!(Text::from("\u{d7ff}") < surrogate);
    }

    #[test]
    fn integers_are_written_in_full_whatever_their_size() {
        let cap: BigInt = "99999999999999999999".parse().expect("a decimal literal");

        assert_eq!(dumps(&Value::Int(cap)), "99999999999999999999");
    }

    #[test]
    fn objects_are_sorted_by_key_and_written_without_spaces() {
        let object = |fields: Vec<(&str, Value)>| {
            Value::Object(
                fields
                    .into_iter()
                    .map(|(key, value)| (key.to_string(), value))
                    .collect::<BTreeMap<_, _>>(),
            )
        };
        let document = object(vec![
            (
                "b",
                Value::Array(vec![
                    Value::Int(BigInt::from(1)),
                    Value::Int(BigInt::from(-2)),
                    Value::Null,
                    Value::Bool(true),
                    Value::Bool(false),
                ]),
            ),
            ("B", object(vec![])),
            ("a", Value::Array(vec![])),
            ("\u{e9}", Value::Str("x".into())),
            (
                "Z",
                object(vec![
                    ("y", Value::Int(BigInt::from(1))),
                    (
                        "x",
                        Value::Array(vec![object(vec![("k", Value::Str("v".into()))])]),
                    ),
                ]),
            ),
        ]);

        assert_eq!(
            dumps(&document),
            "{\"B\":{},\"Z\":{\"x\":[{\"k\":\"v\"}],\"y\":1},\"a\":[],\"b\":[1,-2,null,true,false],\"\\u00e9\":\"x\"}"
        );
    }
}
