#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Object,
    Array,
    String,
    Number,
    Literal,
}

pub struct Member {
    pub key: Vec<u32>,
    pub kind: Kind,
    pub text: (usize, usize),
    pub string: Option<Vec<u32>>,
}

pub enum Top {
    Object(Vec<Member>),
    Other,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Expected {
    NoByteOrderMark,
    Value,
    PropertyName,
    Colon,
    Comma,
    NoTrailingComma,
    StringEnd,
    NoControlCharacter,
    Escape,
    HexDigits,
    End,
}

impl Expected {
    pub fn describe(self) -> &'static str {
        match self {
            Expected::NoByteOrderMark => "a byte order mark begins the text",
            Expected::Value => "expected a value",
            Expected::PropertyName => "expected a property name in double quotes",
            Expected::Colon => "expected ':'",
            Expected::Comma => "expected ',' or the end of the object or array",
            Expected::NoTrailingComma => "a comma ends the object or array",
            Expected::StringEnd => "the string does not end",
            Expected::NoControlCharacter => "a control character is in a string",
            Expected::Escape => "an invalid escape",
            Expected::HexDigits => "expected four hex digits after \\u",
            Expected::End => "text after the value",
        }
    }
}

pub enum Refusal {
    NotJson { expected: Expected, at: usize },
    Constant(&'static str),
}

const CONSTANTS: [&str; 3] = ["NaN", "Infinity", "-Infinity"];
const LITERALS: [&str; 3] = ["true", "false", "null"];
const HIGH_SURROGATES: std::ops::RangeInclusive<u32> = 0xd800..=0xdbff;
const LOW_SURROGATES: std::ops::RangeInclusive<u32> = 0xdc00..=0xdfff;
const SURROGATE_BASE: u32 = 0x10000;
const SURROGATE_SHIFT: u32 = 10;
const CONTROL_END: u8 = 0x20;

enum Frame {
    Object { start: usize, key: Vec<u32> },
    Array { start: usize },
}

struct Reader<'a> {
    text: &'a [u8],
    at: usize,
}

impl Reader<'_> {
    fn refuse<T>(&self, expected: Expected) -> Result<T, Refusal> {
        Err(Refusal::NotJson {
            expected,
            at: self.at,
        })
    }

    fn peek(&self) -> Option<u8> {
        self.text.get(self.at).copied()
    }

    fn eat(&mut self, byte: u8) -> bool {
        if self.peek() == Some(byte) {
            self.at += 1;
            return true;
        }
        false
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.at += 1;
        }
    }

    fn rest_starts_with(&self, word: &str) -> bool {
        self.text[self.at..].starts_with(word.as_bytes())
    }

    fn digits(&mut self) -> usize {
        let start = self.at;
        while matches!(self.peek(), Some(b'0'..=b'9')) {
            self.at += 1;
        }
        self.at - start
    }

    fn number(&mut self) -> Result<(), Refusal> {
        let start = self.at;
        self.eat(b'-');
        match self.peek() {
            Some(b'0') => self.at += 1,
            Some(b'1'..=b'9') => {
                self.digits();
            }
            _ => {
                self.at = start;
                return self.refuse(Expected::Value);
            }
        }
        let fraction = self.at;
        if self.eat(b'.') && self.digits() == 0 {
            self.at = fraction;
        }
        let exponent = self.at;
        if matches!(self.peek(), Some(b'e' | b'E')) {
            self.at += 1;
            if !self.eat(b'+') {
                self.eat(b'-');
            }
            if self.digits() == 0 {
                self.at = exponent;
            }
        }
        Ok(())
    }

    fn hex_unit(&mut self) -> Result<u32, Refusal> {
        let digits = self.text.get(self.at..self.at + 4);
        let Some(digits) = digits.filter(|digits| digits.iter().all(u8::is_ascii_hexdigit)) else {
            return self.refuse(Expected::HexDigits);
        };
        let text = std::str::from_utf8(digits).expect("hex digits are ASCII");
        self.at += 4;
        Ok(u32::from_str_radix(text, 16).expect("four hex digits"))
    }

    fn string(&mut self) -> Result<Vec<u32>, Refusal> {
        let start = self.at;
        assert!(self.eat(b'"'));
        let mut points = Vec::new();
        loop {
            let Some(byte) = self.peek() else {
                self.at = start;
                return self.refuse(Expected::StringEnd);
            };
            match byte {
                b'"' => {
                    self.at += 1;
                    return Ok(points);
                }
                b'\\' => {
                    self.at += 1;
                    let point = match self.peek() {
                        Some(b'"') => u32::from(b'"'),
                        Some(b'\\') => u32::from(b'\\'),
                        Some(b'/') => u32::from(b'/'),
                        Some(b'b') => 0x08,
                        Some(b'f') => 0x0c,
                        Some(b'n') => u32::from(b'\n'),
                        Some(b'r') => u32::from(b'\r'),
                        Some(b't') => u32::from(b'\t'),
                        Some(b'u') => {
                            self.at += 1;
                            let unit = self.hex_unit()?;
                            points.push(self.after_unit(unit));
                            continue;
                        }
                        None => {
                            self.at = start;
                            return self.refuse(Expected::StringEnd);
                        }
                        Some(_) => return self.refuse(Expected::Escape),
                    };
                    self.at += 1;
                    points.push(point);
                }
                byte if byte < CONTROL_END => return self.refuse(Expected::NoControlCharacter),
                _ => {
                    let rest = std::str::from_utf8(&self.text[self.at..])
                        .expect("the reader reads UTF-8 text");
                    let character = rest.chars().next().expect("a character");
                    self.at += character.len_utf8();
                    points.push(u32::from(character));
                }
            }
        }
    }

    fn after_unit(&mut self, unit: u32) -> u32 {
        if !HIGH_SURROGATES.contains(&unit) || !self.rest_starts_with("\\u") {
            return unit;
        }
        let before = self.at;
        self.at += 2;
        match self.hex_unit() {
            Ok(low) if LOW_SURROGATES.contains(&low) => {
                SURROGATE_BASE
                    + ((unit - HIGH_SURROGATES.start()) << SURROGATE_SHIFT)
                    + (low - LOW_SURROGATES.start())
            }
            _ => {
                self.at = before;
                unit
            }
        }
    }

    fn key(&mut self) -> Result<Vec<u32>, Refusal> {
        if self.peek() != Some(b'"') {
            return self.refuse(Expected::PropertyName);
        }
        let key = self.string()?;
        self.skip_whitespace();
        if !self.eat(b':') {
            return self.refuse(Expected::Colon);
        }
        Ok(key)
    }

    fn scalar(&mut self) -> Result<(Kind, Option<Vec<u32>>), Refusal> {
        if let Some(constant) = CONSTANTS
            .into_iter()
            .find(|word| self.rest_starts_with(word))
        {
            return Err(Refusal::Constant(constant));
        }
        if let Some(literal) = LITERALS
            .into_iter()
            .find(|word| self.rest_starts_with(word))
        {
            self.at += literal.len();
            return Ok((Kind::Literal, None));
        }
        match self.peek() {
            Some(b'"') => Ok((Kind::String, Some(self.string()?))),
            Some(b'-' | b'0'..=b'9') => {
                self.number()?;
                Ok((Kind::Number, None))
            }
            _ => self.refuse(Expected::Value),
        }
    }
}

pub fn read(text: &str) -> Result<Top, Refusal> {
    let mut reader = Reader {
        text: text.as_bytes(),
        at: 0,
    };
    if text.starts_with('\u{feff}') {
        return reader.refuse(Expected::NoByteOrderMark);
    }
    let mut frames: Vec<Frame> = Vec::new();
    let mut members = Vec::new();
    let top = 'value: loop {
        reader.skip_whitespace();
        let start = reader.at;
        let (mut kind, mut string) = match reader.peek() {
            Some(b'{') => {
                reader.at += 1;
                reader.skip_whitespace();
                if reader.eat(b'}') {
                    (Kind::Object, None)
                } else {
                    let key = reader.key()?;
                    frames.push(Frame::Object { start, key });
                    continue 'value;
                }
            }
            Some(b'[') => {
                reader.at += 1;
                reader.skip_whitespace();
                if reader.eat(b']') {
                    (Kind::Array, None)
                } else {
                    frames.push(Frame::Array { start });
                    continue 'value;
                }
            }
            _ => reader.scalar()?,
        };
        let mut value_start = start;
        loop {
            let depth = frames.len();
            let Some(frame) = frames.last_mut() else {
                break 'value kind;
            };
            let value_end = reader.at;
            reader.skip_whitespace();
            match frame {
                Frame::Object { start, key } => {
                    if depth == 1 {
                        members.push(Member {
                            key: std::mem::take(key),
                            kind,
                            text: (value_start, value_end),
                            string: string.take(),
                        });
                    }
                    if reader.eat(b',') {
                        reader.skip_whitespace();
                        if reader.peek() == Some(b'}') {
                            return reader.refuse(Expected::NoTrailingComma);
                        }
                        *key = reader.key()?;
                        continue 'value;
                    }
                    if !reader.eat(b'}') {
                        return reader.refuse(Expected::Comma);
                    }
                    value_start = *start;
                    kind = Kind::Object;
                }
                Frame::Array { start } => {
                    if reader.eat(b',') {
                        reader.skip_whitespace();
                        if reader.peek() == Some(b']') {
                            return reader.refuse(Expected::NoTrailingComma);
                        }
                        continue 'value;
                    }
                    if !reader.eat(b']') {
                        return reader.refuse(Expected::Comma);
                    }
                    value_start = *start;
                    kind = Kind::Array;
                }
            }
            string = None;
            frames.pop();
        }
    };
    reader.skip_whitespace();
    if reader.at != text.len() {
        return reader.refuse(Expected::End);
    }
    Ok(match top {
        Kind::Object => Top::Object(members),
        _ => Top::Other,
    })
}
