use num_bigint::BigInt;

use crate::text::{Unit, decimal, is_space_not_ascii, units};

pub const INT_DIGITS_MAX: usize = 4300;
const ASCII_END: u32 = 127;
const DECIMAL_BASE: u32 = 10;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum IntError {
    Invalid,
    DigitsPastLimit,
}

fn ascii_form(bytes: &[u8]) -> Result<Vec<u8>, IntError> {
    let mut out = Vec::with_capacity(bytes.len());
    for unit in units(bytes) {
        let Unit::Char(character) = unit else {
            return Err(IntError::Invalid);
        };
        let point = u32::from(character);
        if point < ASCII_END {
            out.push(u8::try_from(point).expect("an ASCII point"));
        } else if is_space_not_ascii(character) {
            out.push(b' ');
        } else if let Some(value) = decimal(character) {
            out.push(b'0' + u8::try_from(value).expect("a digit"));
        } else {
            return Err(IntError::Invalid);
        }
    }
    Ok(out)
}

fn is_python_space(byte: u8) -> bool {
    matches!(byte, b' ' | b'\t' | b'\n' | b'\x0b' | b'\x0c' | b'\r')
}

pub fn python_int(bytes: &[u8]) -> Result<BigInt, IntError> {
    let text = ascii_form(bytes)?;
    let mut index = 0;
    while index < text.len() && is_python_space(text[index]) {
        index += 1;
    }
    let negative = text.get(index) == Some(&b'-');
    if matches!(text.get(index), Some(b'-' | b'+')) {
        index += 1;
    }
    let mut digits = Vec::new();
    while let Some(byte) = text.get(index) {
        if byte.is_ascii_digit() {
            digits.push(*byte);
            index += 1;
        } else if *byte == b'_' && !digits.is_empty() {
            match text.get(index + 1) {
                Some(next) if next.is_ascii_digit() => index += 1,
                _ => return Err(IntError::Invalid),
            }
        } else {
            break;
        }
    }
    while index < text.len() && is_python_space(text[index]) {
        index += 1;
    }
    if digits.is_empty() || index != text.len() {
        return Err(IntError::Invalid);
    }
    if digits.len() > INT_DIGITS_MAX {
        return Err(IntError::DigitsPastLimit);
    }
    let magnitude = BigInt::parse_bytes(&digits, DECIMAL_BASE).expect("decimal digits");
    Ok(if negative { -magnitude } else { magnitude })
}
