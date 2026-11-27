use std::fmt::Write;

use serde_json::Value;

const CODE_POINTS: &str = "\u{0}code points";

pub fn text(code_points: &[u32]) -> Value {
    match code_points
        .iter()
        .map(|&point| char::from_u32(point))
        .collect::<Option<String>>()
    {
        Some(text) => Value::from(text),
        None => serde_json::json!({CODE_POINTS: code_points}),
    }
}

pub fn line(value: &Value) -> String {
    let mut text = String::new();
    write_value(&mut text, value);
    text.push('\n');
    text
}

fn write_value(text: &mut String, value: &Value) {
    match value {
        Value::Null => text.push_str("null"),
        Value::Bool(true) => text.push_str("true"),
        Value::Bool(false) => text.push_str("false"),
        Value::Number(number) => text.push_str(&number.to_string()),
        Value::String(string) => write_string(text, string),
        Value::Array(items) => {
            text.push('[');
            for (index, item) in items.iter().enumerate() {
                if index > 0 {
                    text.push(',');
                }
                write_value(text, item);
            }
            text.push(']');
        }
        Value::Object(map) => {
            if let Some(Value::Array(points)) = map.get(CODE_POINTS) {
                let points = points.iter().map(|point| {
                    let point = point.as_u64().expect("a code point is a number");
                    u32::try_from(point).expect("a code point fits u32")
                });
                write_code_points(text, points);
                return;
            }
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort_by(|a, b| a.chars().cmp(b.chars()));
            text.push('{');
            for (index, key) in keys.into_iter().enumerate() {
                if index > 0 {
                    text.push(',');
                }
                write_string(text, key);
                text.push(':');
                write_value(text, &map[key]);
            }
            text.push('}');
        }
    }
}

fn write_code_points(text: &mut String, points: impl Iterator<Item = u32>) {
    text.push('"');
    for point in points {
        match char::from_u32(point) {
            Some(character) => write_character(text, character),
            None => write!(text, "\\u{point:04x}").expect("a string takes any text"),
        }
    }
    text.push('"');
}

fn write_string(text: &mut String, string: &str) {
    text.push('"');
    for character in string.chars() {
        write_character(text, character);
    }
    text.push('"');
}

fn write_character(text: &mut String, character: char) {
    match character {
        '"' => text.push_str("\\\""),
        '\\' => text.push_str("\\\\"),
        '\n' => text.push_str("\\n"),
        '\r' => text.push_str("\\r"),
        '\t' => text.push_str("\\t"),
        '\u{8}' => text.push_str("\\b"),
        '\u{c}' => text.push_str("\\f"),
        character if (character as u32) < 0x20 || (character as u32) > 0x7e => {
            let mut units = [0u16; 2];
            for unit in character.encode_utf16(&mut units) {
                write!(text, "\\u{unit:04x}").expect("a string takes any text");
            }
        }
        character => text.push(character),
    }
}
