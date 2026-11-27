use std::fmt::Write;

use serde_json::Value;

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

fn write_string(text: &mut String, string: &str) {
    text.push('"');
    for character in string.chars() {
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
    text.push('"');
}
