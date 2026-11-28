use num_bigint::BigInt;
use pycg_document::{Text, Value as Document, dumps};
use serde_json::Value;

const CODE_POINTS: &str = "\u{0}code points";

pub fn line(value: &Value) -> String {
    let mut text = dumps(&document(value).expect("a record is a JSON value of integers"));
    text.push('\n');
    text
}

fn document(value: &Value) -> Result<Document, String> {
    Ok(match value {
        Value::Null => Document::Null,
        Value::Bool(flag) => Document::Bool(*flag),
        Value::Number(number) => Document::Int(integer(number)?),
        Value::String(text) => Document::Str(text.as_str().into()),
        Value::Array(items) => {
            Document::Array(items.iter().map(document).collect::<Result<_, _>>()?)
        }
        Value::Object(fields) => match fields.get(CODE_POINTS) {
            Some(Value::Array(points)) => Document::Str(Text::from_code_points(
                &points
                    .iter()
                    .map(|point| {
                        point
                            .as_u64()
                            .and_then(|point| u32::try_from(point).ok())
                            .ok_or_else(|| format!("{point} is not a code point"))
                    })
                    .collect::<Result<Vec<u32>, String>>()?,
            )),
            _ => Document::Object(
                fields
                    .iter()
                    .map(|(key, field)| Ok((key.clone(), document(field)?)))
                    .collect::<Result<_, String>>()?,
            ),
        },
    })
}

fn integer(number: &serde_json::Number) -> Result<BigInt, String> {
    match (number.as_i64(), number.as_u64()) {
        (Some(signed), _) => Ok(BigInt::from(signed)),
        (None, Some(unsigned)) => Ok(BigInt::from(unsigned)),
        (None, None) => Err(format!("{number} is not an integer")),
    }
}
