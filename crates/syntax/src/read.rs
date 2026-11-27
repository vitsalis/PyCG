use std::io::ErrorKind;
use std::path::Path;

use crate::codecs::{self, Codec, Decoding};

const BOM_UTF8: &[u8] = b"\xef\xbb\xbf";
const DEFAULT_ENCODING: &str = "utf-8";
const DEFAULT_ENCODING_WITH_BOM: &str = "utf-8-sig";
const COOKIE_WORD: &[u8] = b"coding";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReadFailure {
    Os { error: &'static str },
    Syntax,
    Decode { byte: usize },
    UnsupportedCodec { module: String },
}

impl ReadFailure {
    pub fn cause(&self) -> String {
        match self {
            ReadFailure::Os { error } => (*error).to_owned(),
            ReadFailure::Syntax => "SyntaxError".to_owned(),
            ReadFailure::Decode { byte } => format!("UnicodeDecodeError (byte {byte})"),
            ReadFailure::UnsupportedCodec { module } => {
                format!("unsupported encoding {module}")
            }
        }
    }
}

pub fn read_file(path: &Path) -> Result<String, ReadFailure> {
    let bytes = std::fs::read(path).map_err(|error| ReadFailure::Os {
        error: os_error_name(error.kind()),
    })?;
    read_source(&bytes)
}

fn os_error_name(kind: ErrorKind) -> &'static str {
    match kind {
        ErrorKind::NotFound => "FileNotFoundError",
        ErrorKind::PermissionDenied => "PermissionError",
        ErrorKind::IsADirectory => "IsADirectoryError",
        ErrorKind::NotADirectory => "NotADirectoryError",
        _ => "OSError",
    }
}

pub fn read_source(bytes: &[u8]) -> Result<String, ReadFailure> {
    let codec = detect_encoding(bytes)?;
    let text = decode(codec, bytes)?;
    Ok(translate_newlines(&text))
}

fn translate_newlines(text: &str) -> String {
    text.replace("\r\n", "\n").replace('\r', "\n")
}

fn split_line(bytes: &[u8]) -> (&[u8], &[u8]) {
    match bytes.iter().position(|&byte| byte == b'\n') {
        Some(end) => bytes.split_at(end + 1),
        None => (bytes, &[]),
    }
}

fn detect_encoding(bytes: &[u8]) -> Result<&'static Codec, ReadFailure> {
    let (mut first, rest) = split_line(bytes);
    let bom_found = first.starts_with(BOM_UTF8);
    let default = if bom_found {
        DEFAULT_ENCODING_WITH_BOM
    } else {
        DEFAULT_ENCODING
    };
    if bom_found {
        first = &first[BOM_UTF8.len()..];
    }
    let default_codec = codecs::lookup(default).expect("the default codecs exist");
    if first.is_empty() {
        return Ok(default_codec);
    }
    if let Some(codec) = find_cookie(first, bom_found)? {
        check(first, codec)?;
        return Ok(codec);
    }
    if !is_blank(first) {
        check(first, default_codec)?;
        return Ok(default_codec);
    }
    let (second, _) = split_line(rest);
    let both = &bytes[..bytes.len() - rest.len() + second.len()];
    let both = if bom_found {
        &both[BOM_UTF8.len()..]
    } else {
        both
    };
    if second.is_empty() {
        check(first, default_codec)?;
        return Ok(default_codec);
    }
    if let Some(codec) = find_cookie(second, bom_found)? {
        check(both, codec)?;
        return Ok(codec);
    }
    check(both, default_codec)?;
    Ok(default_codec)
}

fn check(lines: &[u8], codec: &'static Codec) -> Result<(), ReadFailure> {
    if lines.contains(&0) {
        return Err(ReadFailure::Syntax);
    }
    match decode(codec, lines) {
        Ok(_) => Ok(()),
        Err(ReadFailure::Decode { .. }) => Err(ReadFailure::Syntax),
        Err(other) => Err(other),
    }
}

fn find_cookie(line: &[u8], bom_found: bool) -> Result<Option<&'static Codec>, ReadFailure> {
    let Some(name) = cookie_name(line) else {
        return Ok(None);
    };
    let encoding = codecs::normal_name(name);
    let Some(codec) = codecs::lookup(&encoding) else {
        return Err(ReadFailure::Syntax);
    };
    if !bom_found {
        return Ok(Some(codec));
    }
    if encoding != DEFAULT_ENCODING {
        return Err(ReadFailure::Syntax);
    }
    Ok(Some(
        codecs::lookup(DEFAULT_ENCODING_WITH_BOM).expect("utf-8-sig exists"),
    ))
}

fn is_space(byte: u8) -> bool {
    matches!(byte, b' ' | b'\t' | b'\x0c')
}

fn is_name_byte(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.')
}

fn is_blank(line: &[u8]) -> bool {
    let start = line.iter().position(|&byte| !is_space(byte));
    match start {
        None => true,
        Some(index) => matches!(line[index], b'#' | b'\r' | b'\n'),
    }
}

fn cookie_name(line: &[u8]) -> Option<&str> {
    let start = line.iter().position(|&byte| !is_space(byte))?;
    if line[start] != b'#' {
        return None;
    }
    let end = line
        .iter()
        .position(|&byte| byte == b'\n')
        .unwrap_or(line.len());
    let comment = &line[start + 1..end];
    (0..comment.len()).find_map(|index| cookie_at(comment, index))
}

fn cookie_at(comment: &[u8], index: usize) -> Option<&str> {
    let rest = comment[index..].strip_prefix(COOKIE_WORD)?;
    let (&separator, rest) = rest.split_first()?;
    if separator != b':' && separator != b'=' {
        return None;
    }
    let spaces = rest
        .iter()
        .take_while(|&&byte| byte == b' ' || byte == b'\t')
        .count();
    let rest = &rest[spaces..];
    let length = rest.iter().take_while(|&&byte| is_name_byte(byte)).count();
    if length == 0 {
        return None;
    }
    Some(std::str::from_utf8(&rest[..length]).expect("a cookie name is ASCII"))
}

fn decode(codec: &'static Codec, bytes: &[u8]) -> Result<String, ReadFailure> {
    match codec.decoding {
        Decoding::Utf8 => decode_utf8(bytes),
        Decoding::Utf8Sig => decode_utf8(bytes.strip_prefix(BOM_UTF8).unwrap_or(bytes)),
        Decoding::Ascii => decode_ascii(bytes),
        Decoding::Latin1 => Ok(bytes.iter().map(|&byte| char::from(byte)).collect()),
        Decoding::Charmap => decode_charmap(codec, bytes),
        Decoding::Unsupported => Err(ReadFailure::UnsupportedCodec {
            module: codec.module.clone(),
        }),
    }
}

fn decode_utf8(bytes: &[u8]) -> Result<String, ReadFailure> {
    match std::str::from_utf8(bytes) {
        Ok(text) => Ok(text.to_owned()),
        Err(error) => Err(ReadFailure::Decode {
            byte: error.valid_up_to(),
        }),
    }
}

fn decode_ascii(bytes: &[u8]) -> Result<String, ReadFailure> {
    match bytes.iter().position(|byte| !byte.is_ascii()) {
        Some(byte) => Err(ReadFailure::Decode { byte }),
        None => Ok(bytes.iter().map(|&byte| char::from(byte)).collect()),
    }
}

fn decode_charmap(codec: &Codec, bytes: &[u8]) -> Result<String, ReadFailure> {
    let table = codec.table.as_ref().expect("a charmap codec has a table");
    let mut text = String::with_capacity(bytes.len());
    for (byte_index, &byte) in bytes.iter().enumerate() {
        match table[usize::from(byte)] {
            Some(character) => text.push(character),
            None => return Err(ReadFailure::Decode { byte: byte_index }),
        }
    }
    Ok(text)
}
