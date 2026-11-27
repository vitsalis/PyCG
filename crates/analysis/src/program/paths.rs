use std::ffi::{OsStr, OsString};
use std::fmt;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PathsError {
    Mounts { path: String, start: String },
    Drives,
    Mixed { rooted: bool },
}

fn python_repr(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::from(quote);
    for character in text.chars() {
        match character {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            character if character == quote => {
                out.push('\\');
                out.push(character);
            }
            character if character < ' ' || character == '\u{7f}' => {
                out.push_str(&format!("\\x{:02x}", u32::from(character)));
            }
            character => out.push(character),
        }
    }
    out.push(quote);
    out
}

impl fmt::Display for PathsError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PathsError::Mounts { path, start } => write!(
                formatter,
                "path is on mount {}, start on mount {}",
                python_repr(path),
                python_repr(start)
            ),
            PathsError::Drives => formatter.write_str("Paths don't have the same drive"),
            PathsError::Mixed { rooted: false } => {
                formatter.write_str("Can't mix absolute and relative paths")
            }
            PathsError::Mixed { rooted: true } => {
                formatter.write_str("Can't mix rooted and not-rooted paths")
            }
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Flavour {
    Posix,
    Nt,
}

pub const FLAVOUR: Flavour = if cfg!(windows) {
    Flavour::Nt
} else {
    Flavour::Posix
};

const CURDIR: &[u8] = b".";
const PARDIR: &[u8] = b"..";
const EXTSEP: u8 = b'.';
const COLON: u8 = b':';
const SLASH: u8 = b'/';
const BACKSLASH: u8 = b'\\';
const UNC_PREFIX: &[u8] = b"\\\\?\\UNC\\";

impl Flavour {
    pub fn sep(self) -> u8 {
        match self {
            Flavour::Posix => SLASH,
            Flavour::Nt => BACKSLASH,
        }
    }

    fn is_sep(self, byte: u8) -> bool {
        match self {
            Flavour::Posix => byte == SLASH,
            Flavour::Nt => byte == SLASH || byte == BACKSLASH,
        }
    }

    fn with_sep(self, path: &[u8]) -> Vec<u8> {
        let sep = self.sep();
        path.iter()
            .map(|&byte| if self.is_sep(byte) { sep } else { byte })
            .collect()
    }

    fn splitroot(self, path: &[u8]) -> (Vec<u8>, Vec<u8>, Vec<u8>) {
        match self {
            Flavour::Posix => {
                let slashes = path.iter().take_while(|&&byte| byte == SLASH).count();
                let root = if slashes == 2 { 2 } else { slashes.min(1) };
                (Vec::new(), path[..root].to_vec(), path[root..].to_vec())
            }
            Flavour::Nt => nt_splitroot(path),
        }
    }

    fn normcase(self, part: &[u8]) -> Vec<u8> {
        match self {
            Flavour::Posix => part.to_vec(),
            Flavour::Nt => lowercase(&self.with_sep(part)),
        }
    }

    fn is_absolute(self, path: &[u8]) -> bool {
        match self {
            Flavour::Posix => path.first() == Some(&SLASH),
            Flavour::Nt => {
                let head = self.with_sep(&path[..path.len().min(3)]);
                head.starts_with(&[BACKSLASH, BACKSLASH])
                    || (head.len() == 3 && head[1] == COLON && head[2] == BACKSLASH)
            }
        }
    }
}

fn lowercase(text: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(text.len());
    for chunk in text.utf8_chunks() {
        out.extend(chunk.valid().to_lowercase().into_bytes());
        out.extend(chunk.invalid());
    }
    out
}

fn nt_splitroot(path: &[u8]) -> (Vec<u8>, Vec<u8>, Vec<u8>) {
    let normal = Flavour::Nt.with_sep(path);
    let find = |from: usize| {
        normal
            .get(from..)
            .and_then(|rest| rest.iter().position(|&byte| byte == BACKSLASH))
            .map(|index| index + from)
    };
    if normal.first() == Some(&BACKSLASH) {
        if normal.get(1) != Some(&BACKSLASH) {
            return (Vec::new(), path[..1].to_vec(), path[1..].to_vec());
        }
        let unc = normal.len() >= UNC_PREFIX.len()
            && normal[..UNC_PREFIX.len()].eq_ignore_ascii_case(UNC_PREFIX);
        let start = if unc { UNC_PREFIX.len() } else { 2 };
        let Some(first) = find(start) else {
            return (path.to_vec(), Vec::new(), Vec::new());
        };
        let Some(second) = find(first + 1) else {
            return (path.to_vec(), Vec::new(), Vec::new());
        };
        return (
            path[..second].to_vec(),
            path[second..=second].to_vec(),
            path[second + 1..].to_vec(),
        );
    }
    if normal.get(1) == Some(&COLON) {
        if normal.get(2) == Some(&BACKSLASH) {
            return (path[..2].to_vec(), path[2..3].to_vec(), path[3..].to_vec());
        }
        return (path[..2].to_vec(), Vec::new(), path[2..].to_vec());
    }
    (Vec::new(), Vec::new(), path.to_vec())
}

#[cfg(unix)]
fn os_str(bytes: &[u8]) -> &OsStr {
    std::os::unix::ffi::OsStrExt::from_bytes(bytes)
}

#[cfg(not(unix))]
fn os_str(bytes: &[u8]) -> &OsStr {
    unsafe { OsStr::from_encoded_bytes_unchecked(bytes) }
}

fn os_string(bytes: Vec<u8>) -> OsString {
    os_str(&bytes).to_os_string()
}

fn bytes(path: &Path) -> &[u8] {
    path.as_os_str().as_encoded_bytes()
}

fn normpath_in(flavour: Flavour, path: &[u8]) -> Vec<u8> {
    if path.is_empty() {
        return CURDIR.to_vec();
    }
    let path = flavour.with_sep(path);
    let (drive, root, tail) = flavour.splitroot(&path);
    let mut parts: Vec<&[u8]> = Vec::new();
    for part in tail.split(|&byte| byte == flavour.sep()) {
        if part.is_empty() || part == CURDIR {
            continue;
        }
        if part != PARDIR {
            parts.push(part);
        } else if parts.last().is_some_and(|&last| last != PARDIR) {
            parts.pop();
        } else if root.is_empty() {
            parts.push(part);
        }
    }
    let mut out = [drive, root].concat();
    out.extend(parts.join(&flavour.sep()));
    if out.is_empty() {
        out.extend(CURDIR);
    }
    out
}

fn join_in(flavour: Flavour, path: &[u8], other: &[u8]) -> Vec<u8> {
    match flavour {
        Flavour::Posix => {
            if other.first() == Some(&SLASH) {
                return other.to_vec();
            }
            let mut out = path.to_vec();
            if !out.is_empty() && out.last() != Some(&SLASH) {
                out.push(SLASH);
            }
            out.extend(other);
            out
        }
        Flavour::Nt => {
            let (mut drive, mut root, mut tail) = nt_splitroot(path);
            let (other_drive, other_root, other_tail) = nt_splitroot(other);
            if !other_root.is_empty() {
                if !other_drive.is_empty() || drive.is_empty() {
                    drive = other_drive;
                }
                root = other_root;
                tail = other_tail;
            } else {
                if !other_drive.is_empty() && other_drive != drive {
                    if lowercase(&other_drive) != lowercase(&drive) {
                        return [other_drive, other_root, other_tail].concat();
                    }
                    drive = other_drive;
                }
                if tail.last().is_some_and(|&byte| !flavour.is_sep(byte)) {
                    tail.push(BACKSLASH);
                }
                tail.extend(other_tail);
            }
            let separated = drive
                .last()
                .is_some_and(|&byte| byte != COLON && !flavour.is_sep(byte));
            if !tail.is_empty() && root.is_empty() && separated {
                return [drive, vec![BACKSLASH], tail].concat();
            }
            [drive, root, tail].concat()
        }
    }
}

fn abspath_in(flavour: Flavour, path: &[u8], cwd: &[u8]) -> Vec<u8> {
    if flavour.is_absolute(path) {
        normpath_in(flavour, path)
    } else {
        normpath_in(flavour, &join_in(flavour, cwd, path))
    }
}

fn split_in(flavour: Flavour, path: &[u8]) -> (Vec<u8>, Vec<u8>) {
    let (drive, root, tail) = flavour.splitroot(path);
    let index = tail
        .iter()
        .rposition(|&byte| flavour.is_sep(byte))
        .map_or(0, |index| index + 1);
    let (head, name) = tail.split_at(index);
    let kept = head.len()
        - head
            .iter()
            .rev()
            .take_while(|&&byte| flavour.is_sep(byte))
            .count();
    let head = match flavour {
        Flavour::Posix if kept == 0 => head,
        _ => &head[..kept],
    };
    ([drive, root, head.to_vec()].concat(), name.to_vec())
}

fn relpath_in(
    flavour: Flavour,
    path: &[u8],
    start: &[u8],
    cwd: &[u8],
) -> Result<Vec<u8>, PathsError> {
    let (start_drive, _, start_rest) = flavour.splitroot(&abspath_in(flavour, start, cwd));
    let (path_drive, _, path_rest) = flavour.splitroot(&abspath_in(flavour, path, cwd));
    if flavour.normcase(&start_drive) != flavour.normcase(&path_drive) {
        let text = |drive: &[u8]| String::from_utf8_lossy(drive).into_owned();
        return Err(PathsError::Mounts {
            path: text(&path_drive),
            start: text(&start_drive),
        });
    }
    let parts = |rest: &[u8]| -> Vec<Vec<u8>> {
        rest.split(|&byte| flavour.is_sep(byte))
            .filter(|part| !part.is_empty())
            .map(<[u8]>::to_vec)
            .collect()
    };
    let start_parts = parts(&start_rest);
    let path_parts = parts(&path_rest);
    let common = start_parts
        .iter()
        .zip(&path_parts)
        .take_while(|(a, b)| flavour.normcase(a) == flavour.normcase(b))
        .count();
    let mut relative: Vec<Vec<u8>> = vec![PARDIR.to_vec(); start_parts.len() - common];
    relative.extend(path_parts[common..].iter().cloned());
    if relative.is_empty() {
        return Ok(CURDIR.to_vec());
    }
    Ok(relative.join(&flavour.sep()))
}

fn commonpath_in(flavour: Flavour, paths: &[&[u8]]) -> Result<Vec<u8>, PathsError> {
    assert!(!paths.is_empty(), "commonpath takes paths");
    let splits: Vec<(Vec<u8>, Vec<u8>, Vec<u8>)> = paths
        .iter()
        .map(|path| flavour.splitroot(&flavour.normcase(&flavour.with_sep(path))))
        .collect();
    if !splits.iter().all(|(drive, _, _)| *drive == splits[0].0) {
        return Err(PathsError::Drives);
    }
    if !splits
        .iter()
        .all(|(_, root, _)| root.is_empty() == splits[0].1.is_empty())
    {
        let rooted = flavour == Flavour::Nt && splits[0].0.is_empty();
        return Err(PathsError::Mixed { rooted });
    }
    let parts = |rest: &[u8]| -> Vec<Vec<u8>> {
        rest.split(|&byte| byte == flavour.sep())
            .filter(|part| !part.is_empty() && *part != CURDIR)
            .map(<[u8]>::to_vec)
            .collect()
    };
    let lowered: Vec<Vec<Vec<u8>>> = splits.iter().map(|(_, _, rest)| parts(rest)).collect();
    let first = lowered.iter().min().expect("a path");
    let last = lowered.iter().max().expect("a path");
    let common = first.iter().zip(last).take_while(|(a, b)| a == b).count();
    let (drive, root, rest) = flavour.splitroot(&flavour.with_sep(paths[0]));
    let root = match flavour {
        Flavour::Posix if !root.is_empty() => vec![SLASH],
        _ => root,
    };
    let original = parts(&rest);
    let mut out = [drive, root].concat();
    out.extend(original[..common].join(&flavour.sep()));
    Ok(out)
}

pub fn normpath(path: &Path) -> PathBuf {
    PathBuf::from(os_string(normpath_in(FLAVOUR, bytes(path))))
}

pub fn abspath(path: &Path, cwd: &Path) -> PathBuf {
    PathBuf::from(os_string(abspath_in(FLAVOUR, bytes(path), bytes(cwd))))
}

pub fn split(path: &str) -> (String, String) {
    let (head, name) = split_in(FLAVOUR, path.as_bytes());
    let text = |part: Vec<u8>| String::from_utf8(part).expect("a split of UTF-8 is UTF-8");
    (text(head), text(name))
}

pub fn basename(path: &Path) -> OsString {
    os_string(split_in(FLAVOUR, bytes(path)).1)
}

pub fn dirname(path: &Path) -> PathBuf {
    PathBuf::from(os_string(split_in(FLAVOUR, bytes(path)).0))
}

pub fn relpath(path: &Path, start: &Path, cwd: &Path) -> Result<PathBuf, PathsError> {
    relpath_in(FLAVOUR, bytes(path), bytes(start), bytes(cwd))
        .map(|relative| PathBuf::from(os_string(relative)))
}

pub fn commonpath(paths: &[PathBuf]) -> Result<PathBuf, PathsError> {
    let paths: Vec<&[u8]> = paths.iter().map(|path| bytes(path)).collect();
    commonpath_in(FLAVOUR, &paths).map(|common| PathBuf::from(os_string(common)))
}

pub fn splitext(name: &str) -> (&str, &str) {
    let bytes = name.as_bytes();
    let leading = bytes.iter().take_while(|&&byte| byte == EXTSEP).count();
    match bytes[leading..].iter().rposition(|&byte| byte == EXTSEP) {
        Some(index) => name.split_at(leading + index),
        None => (name, ""),
    }
}

#[cfg(test)]
#[path = "path_vectors.rs"]
mod path_vectors;

#[cfg(test)]
mod tests {
    use super::path_vectors::{CASES, Case};
    use super::*;

    fn text(bytes: &[u8]) -> String {
        String::from_utf8_lossy(bytes).into_owned()
    }

    fn shown(result: Result<Vec<u8>, PathsError>) -> String {
        match result {
            Ok(path) => text(&path),
            Err(error) => format!("ValueError: {error}"),
        }
    }

    fn run(case: &Case) -> String {
        let flavour = match case.flavour {
            "posix" => Flavour::Posix,
            "nt" => Flavour::Nt,
            other => unreachable!("flavour {other}"),
        };
        let arguments: Vec<&[u8]> = case.arguments.iter().map(|a| a.as_bytes()).collect();
        match (case.function, arguments.as_slice()) {
            ("normpath", [path]) => text(&normpath_in(flavour, path)),
            ("abspath", [path, cwd]) => text(&abspath_in(flavour, path, cwd)),
            ("join", [path, other]) => text(&join_in(flavour, path, other)),
            ("split", [path]) => {
                let (head, name) = split_in(flavour, path);
                format!("{}|{}", text(&head), text(&name))
            }
            ("relpath", [path, start, cwd]) => shown(relpath_in(flavour, path, start, cwd)),
            ("commonpath", paths) => shown(commonpath_in(flavour, paths)),
            ("splitext", [name]) => {
                let (stem, suffix) = splitext(std::str::from_utf8(name).expect("UTF-8"));
                format!("{stem}|{suffix}")
            }
            (function, _) => unreachable!("function {function}"),
        }
    }

    #[test]
    fn every_path_function_gives_what_python_gives() {
        let failures: Vec<String> = CASES
            .iter()
            .filter_map(|case| {
                let found = run(case);
                (found != case.expected).then(|| {
                    format!(
                        "{} {}{:?}: {found:?}, Python {:?}",
                        case.flavour, case.function, case.arguments, case.expected
                    )
                })
            })
            .collect();
        assert!(
            failures.is_empty(),
            "{} of {} cases differ:\n{}",
            failures.len(),
            CASES.len(),
            failures.join("\n")
        );
    }
}
