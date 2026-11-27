use num_bigint::BigInt;
use ruff_python_ast::{
    BytesLiteral, DebugText, Expr, InterpolatedStringLiteralElement, Number, StringFlags,
    StringLiteral,
};
use ruff_text_size::{Ranged, TextRange};

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct PyStr(Vec<u32>);

impl PyStr {
    pub fn code_points(&self) -> &[u32] {
        &self.0
    }
}

#[derive(Clone, Debug, PartialEq)]
pub enum Constant {
    None,
    Bool(bool),
    Ellipsis,
    Int(BigInt),
    Float(f64),
    Complex { real: f64, imag: f64 },
    Str(PyStr),
    Bytes(Vec<u8>),
}

#[derive(Clone, Copy, Debug)]
pub enum Text<'a> {
    Literal(&'a StringLiteral),
    Element {
        element: &'a InterpolatedStringLiteralElement,
        raw: bool,
    },
    Debug(&'a DebugText),
}

pub fn literal(expression: &Expr, source: &str) -> Option<Constant> {
    let constant = match expression {
        Expr::NoneLiteral(_) => Constant::None,
        Expr::BooleanLiteral(literal) => Constant::Bool(literal.value),
        Expr::EllipsisLiteral(_) => Constant::Ellipsis,
        Expr::NumberLiteral(literal) => number(&literal.value, &source[literal.range()]),
        Expr::StringLiteral(literal) => {
            let mut code_points = Vec::new();
            for part in literal.value.iter() {
                code_points.extend(string_literal(part, source));
            }
            Constant::Str(PyStr(code_points))
        }
        Expr::BytesLiteral(literal) => {
            let mut bytes = Vec::new();
            for part in literal.value.iter() {
                bytes.extend(bytes_literal(part, source));
            }
            Constant::Bytes(bytes)
        }
        _ => return None,
    };
    Some(constant)
}

pub fn text_value(texts: &[Text<'_>], source: &str) -> PyStr {
    let mut code_points = Vec::new();
    for text in texts {
        match *text {
            Text::Literal(literal) => code_points.extend(string_literal(literal, source)),
            Text::Element { element, raw } => {
                let content = &source[element.range()];
                code_points.extend(decode(content, raw, Braces::Doubled, &element.value));
            }
            Text::Debug(debug) => code_points.extend(debug.as_str().chars().map(u32::from)),
        }
    }
    PyStr(code_points)
}

fn number(value: &Number, text: &str) -> Constant {
    match value {
        Number::Int(_) => Constant::Int(integer(text)),
        Number::Float(value) => Constant::Float(*value),
        Number::Complex { real, imag } => Constant::Complex {
            real: *real,
            imag: *imag,
        },
    }
}

const HEXADECIMAL: u32 = 16;
const OCTAL: u32 = 8;
const BINARY: u32 = 2;
const DECIMAL: u32 = 10;

fn integer(text: &str) -> BigInt {
    let digits: String = text
        .chars()
        .filter(|&c| c != '_')
        .collect::<String>()
        .to_ascii_lowercase();
    let (radix, digits) = match digits.get(..2) {
        Some("0x") => (HEXADECIMAL, &digits[2..]),
        Some("0o") => (OCTAL, &digits[2..]),
        Some("0b") => (BINARY, &digits[2..]),
        _ => (DECIMAL, digits.as_str()),
    };
    BigInt::parse_bytes(digits.as_bytes(), radix).expect("the parser accepted the integer")
}

fn content(range: TextRange, opener: u32, closer: u32, source: &str) -> &str {
    let start = usize::from(range.start()) + opener as usize;
    let end = usize::from(range.end()) - closer as usize;
    &source[start..end]
}

fn string_literal(literal: &StringLiteral, source: &str) -> Vec<u32> {
    let flags = literal.flags;
    let text = content(
        literal.range(),
        flags.opener_len().into(),
        flags.closer_len().into(),
        source,
    );
    decode(
        text,
        flags.prefix().is_raw(),
        Braces::Single,
        &literal.value,
    )
}

fn bytes_literal(literal: &BytesLiteral, source: &str) -> Vec<u8> {
    let flags = literal.flags;
    let text = content(
        literal.range(),
        flags.opener_len().into(),
        flags.closer_len().into(),
        source,
    );
    if flags.prefix().is_raw() {
        return text.bytes().collect();
    }
    decode_bytes(text)
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Braces {
    Single,
    Doubled,
}

const OCTAL_DIGITS_MAX: usize = 3;

fn decode(text: &str, raw: bool, braces: Braces, decoded: &str) -> Vec<u32> {
    let characters: Vec<char> = text.chars().collect();
    let decoded: Vec<char> = decoded.chars().collect();
    let mut found: Vec<u32> = Vec::with_capacity(characters.len());
    let mut index = 0;
    while index < characters.len() {
        let character = characters[index];
        index += 1;
        if braces == Braces::Doubled && (character == '{' || character == '}') {
            if characters.get(index) == Some(&character) {
                index += 1;
            }
            found.push(u32::from(character));
            continue;
        }
        if raw || character != '\\' || index == characters.len() {
            found.push(u32::from(character));
            continue;
        }
        let escape = characters[index];
        index += 1;
        match escape {
            '\n' => {}
            'N' => {
                let close = characters[index..]
                    .iter()
                    .position(|&c| c == '}')
                    .expect("a name ends");
                index += close + 1;
                let named = decoded
                    .get(found.len())
                    .expect("the parser decoded the name");
                found.push(u32::from(*named));
            }
            'x' | 'u' | 'U' => {
                let length = match escape {
                    'x' => 2,
                    'u' => 4,
                    _ => 8,
                };
                let hex: String = characters[index..index + length].iter().collect();
                index += length;
                found.push(u32::from_str_radix(&hex, 16).expect("the parser accepted the escape"));
            }
            '0'..='7' => {
                let digits = octal_length(&characters[index - 1..]);
                let octal: String = characters[index - 1..index - 1 + digits].iter().collect();
                index += digits - 1;
                found.push(u32::from_str_radix(&octal, 8).expect("octal digits"));
            }
            _ => match simple_escape(escape) {
                Some(value) => found.push(value),
                None => {
                    found.push(u32::from('\\'));
                    found.push(u32::from(escape));
                }
            },
        }
    }
    found
}

fn octal_length(characters: &[char]) -> usize {
    characters
        .iter()
        .take(OCTAL_DIGITS_MAX)
        .take_while(|c| ('0'..='7').contains(c))
        .count()
}

fn simple_escape(escape: char) -> Option<u32> {
    let value = match escape {
        '\\' => '\\',
        '\'' => '\'',
        '"' => '"',
        'a' => '\x07',
        'b' => '\x08',
        'f' => '\x0c',
        'n' => '\n',
        'r' => '\r',
        't' => '\t',
        'v' => '\x0b',
        _ => return None,
    };
    Some(u32::from(value))
}

const BYTE_MASK: u32 = 0xff;

fn decode_bytes(text: &str) -> Vec<u8> {
    let bytes = text.as_bytes();
    let mut found = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        let byte = bytes[index];
        index += 1;
        if byte != b'\\' || index == bytes.len() {
            found.push(byte);
            continue;
        }
        let escape = bytes[index];
        index += 1;
        match escape {
            b'\n' => {}
            b'x' => {
                let hex = std::str::from_utf8(&bytes[index..index + 2]).expect("ASCII hex");
                index += 2;
                found.push(u8::from_str_radix(hex, 16).expect("the parser accepted the escape"));
            }
            b'0'..=b'7' => {
                let digits = bytes[index - 1..]
                    .iter()
                    .take(OCTAL_DIGITS_MAX)
                    .take_while(|b| (b'0'..=b'7').contains(b))
                    .count();
                let octal =
                    std::str::from_utf8(&bytes[index - 1..index - 1 + digits]).expect("ASCII");
                index += digits - 1;
                let value = u32::from_str_radix(octal, 8).expect("octal digits") & BYTE_MASK;
                found.push(u8::try_from(value).expect("masked to a byte"));
            }
            _ => match simple_escape(char::from(escape)) {
                Some(value) => found.push(u8::try_from(value).expect("a simple escape is ASCII")),
                None => {
                    found.push(b'\\');
                    found.push(escape);
                }
            },
        }
    }
    found
}
