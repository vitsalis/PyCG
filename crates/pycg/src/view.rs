use std::ffi::{OsStr, OsString};
use std::io;
use std::path::{Component, Path, PathBuf};

use pycg_document::FORMAT;

use crate::ViewOptions;
use crate::arguments::os_string;
use crate::json::{self, Expected, Kind, Member, Refusal, Top};

const TEMPLATE: &str = include_str!("../../../pycg/view/template.html");
const MARKER: &str = "@@PYCG_DOCUMENT@@";
const SUFFIX: &[u8] = b".html";
const SCRIPT_SAFE_LESS_THAN: &str = "\\u003c";
const PARTS: [&str; 7] = [
    "tool",
    "package",
    "modules",
    "definitions",
    "exports",
    "outside",
    "calls",
];

pub enum DocumentError {
    Unreadable(io::Error),
    NotUtf8,
    NotJson {
        expected: Expected,
        line: usize,
        column: usize,
    },
    Constant(&'static str),
    NotObject,
    NoFormat,
    OtherFormat(String),
    NoPart(&'static str),
}

pub enum ViewError {
    EmptyName(OsString),
    WouldOverwrite(PathBuf),
    Document(OsString, DocumentError),
    Unwritable(PathBuf, io::Error),
}

fn strerror(error: &io::Error) -> String {
    let Some(code) = error.raw_os_error() else {
        return error.to_string();
    };
    let text = io::Error::from_raw_os_error(code).to_string();
    let suffix = format!(" (os error {code})");
    text.strip_suffix(&suffix).unwrap_or(&text).to_owned()
}

impl DocumentError {
    fn describe(&self) -> String {
        match self {
            DocumentError::Unreadable(error) => format!("cannot be read: {}", strerror(error)),
            DocumentError::NotUtf8 => "is not UTF-8 text".to_owned(),
            DocumentError::NotJson {
                expected,
                line,
                column,
            } => format!(
                "is not JSON: {} at line {line}, column {column}",
                expected.describe()
            ),
            DocumentError::Constant(name) => {
                format!("is not JSON that a browser reads: it has {name}")
            }
            DocumentError::NotObject => "is not a JSON object".to_owned(),
            DocumentError::NoFormat => {
                "has no 'format': it is not a PyCG call graph document".to_owned()
            }
            DocumentError::OtherFormat(found) => {
                format!("has format {found}; this viewer reads \"{FORMAT}\"")
            }
            DocumentError::NoPart(part) => format!("has no object '{part}'"),
        }
    }
}

impl ViewError {
    pub fn message(&self) -> Vec<u8> {
        match self {
            ViewError::EmptyName(source) => {
                [source.as_encoded_bytes(), b" has an empty name; give -o"].concat()
            }
            ViewError::WouldOverwrite(output) => [
                output.as_os_str().as_encoded_bytes(),
                b" would overwrite the input; give -o",
            ]
            .concat(),
            ViewError::Document(source, error) => {
                [source.as_encoded_bytes(), b" ", error.describe().as_bytes()].concat()
            }
            ViewError::Unwritable(output, error) => [
                b"cannot write ",
                output.as_os_str().as_encoded_bytes(),
                b": ",
                strerror(error).as_bytes(),
            ]
            .concat(),
        }
    }
}

fn stem_length(name: &[u8]) -> usize {
    match name.iter().rposition(|byte| *byte == b'.') {
        Some(dot) if name[..dot].iter().any(|byte| *byte != b'.') => dot,
        _ => name.len(),
    }
}

#[cfg(windows)]
fn same_suffix(suffix: &[u8]) -> bool {
    suffix.eq_ignore_ascii_case(SUFFIX)
}

#[cfg(not(windows))]
fn same_suffix(suffix: &[u8]) -> bool {
    suffix == SUFFIX
}

fn default_output(source: &OsStr) -> Result<PathBuf, ViewError> {
    let mut components: Vec<Component<'_>> = Path::new(source).components().collect();
    let name = match components.pop() {
        Some(Component::Normal(name)) => name.as_encoded_bytes(),
        Some(Component::ParentDir) => b"..",
        Some(Component::CurDir | Component::RootDir | Component::Prefix(_)) | None => {
            return Err(ViewError::EmptyName(source.to_owned()));
        }
    };
    let stem = stem_length(name);
    let mut output: PathBuf = components.iter().collect();
    output.push(os_string(&[&name[..stem], SUFFIX].concat()));
    if same_suffix(&name[stem..]) {
        return Err(ViewError::WouldOverwrite(output));
    }
    Ok(output)
}

fn position(text: &str, at: usize) -> (usize, usize) {
    let before = &text[..at];
    let line_start = before.rfind('\n').map_or(0, |newline| newline + 1);
    let line = before.matches('\n').count() + 1;
    let column = before[line_start..].chars().count() + 1;
    (line, column)
}

fn is(member: &Member, name: &str) -> bool {
    member.key.iter().copied().eq(name.chars().map(u32::from))
}

fn check(text: &str) -> Result<(), DocumentError> {
    let members = match json::read(text) {
        Err(Refusal::NotJson { expected, at }) => {
            let (line, column) = position(text, at);
            return Err(DocumentError::NotJson {
                expected,
                line,
                column,
            });
        }
        Err(Refusal::Constant(name)) => return Err(DocumentError::Constant(name)),
        Ok(Top::Other) => return Err(DocumentError::NotObject),
        Ok(Top::Object(members)) => members,
    };
    let last = |name: &str| members.iter().rev().find(|member| is(member, name));
    let Some(format) = last("format") else {
        return Err(DocumentError::NoFormat);
    };
    let expected: Vec<u32> = FORMAT.chars().map(u32::from).collect();
    if format.string.as_ref() != Some(&expected) {
        let (start, end) = format.text;
        return Err(DocumentError::OtherFormat(text[start..end].to_owned()));
    }
    for part in PARTS {
        if last(part).map(|member| member.kind) != Some(Kind::Object) {
            return Err(DocumentError::NoPart(part));
        }
    }
    Ok(())
}

fn read(source: &OsStr) -> Result<String, DocumentError> {
    let data = std::fs::read(source).map_err(DocumentError::Unreadable)?;
    let text = String::from_utf8(data).map_err(|_| DocumentError::NotUtf8)?;
    check(&text)?;
    Ok(text)
}

fn render(text: &str) -> String {
    let (head, tail) = TEMPLATE
        .split_once(MARKER)
        .expect("the template has the document marker");
    assert!(
        !tail.contains(MARKER),
        "the template has one document marker"
    );
    [head, &text.replace('<', SCRIPT_SAFE_LESS_THAN), tail].concat()
}

pub fn view(options: &ViewOptions) -> Result<(), ViewError> {
    let source = options.document.as_os_str();
    let output = match options
        .output
        .as_deref()
        .filter(|output| !output.is_empty())
    {
        Some(output) => PathBuf::from(output),
        None => default_output(source)?,
    };
    let text = read(source).map_err(|error| ViewError::Document(source.to_owned(), error))?;
    std::fs::write(&output, render(&text)).map_err(|error| ViewError::Unwritable(output, error))
}
