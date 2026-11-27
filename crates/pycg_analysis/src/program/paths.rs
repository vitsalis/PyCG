use std::ffi::{OsStr, OsString};
use std::os::unix::ffi::{OsStrExt, OsStringExt};
use std::path::{Path, PathBuf};

const SEPARATOR: u8 = b'/';

pub fn normpath(path: &Path) -> PathBuf {
    let bytes = path.as_os_str().as_bytes();
    if bytes.is_empty() {
        return PathBuf::from(".");
    }
    let leading = bytes.iter().take_while(|&&byte| byte == SEPARATOR).count();
    let initial: &[u8] = match leading {
        0 => b"",
        2 => b"//",
        _ => b"/",
    };
    let mut parts: Vec<&[u8]> = Vec::new();
    for part in bytes.split(|&byte| byte == SEPARATOR) {
        if part.is_empty() || part == b"." {
            continue;
        }
        let climbs = part == b"..";
        if climbs && !parts.is_empty() && parts.last() != Some(&&b".."[..]) {
            parts.pop();
        } else if !(climbs && !initial.is_empty()) {
            parts.push(part);
        }
    }
    let mut out = initial.to_vec();
    out.extend(parts.join(&SEPARATOR));
    if out.is_empty() {
        out.push(b'.');
    }
    PathBuf::from(OsString::from_vec(out))
}

pub fn abspath(path: &Path, cwd: &Path) -> PathBuf {
    if path.as_os_str().as_bytes().first() == Some(&SEPARATOR) {
        normpath(path)
    } else {
        normpath(&cwd.join(path))
    }
}

pub fn basename(path: &Path) -> &OsStr {
    let bytes = path.as_os_str().as_bytes();
    let start = bytes
        .iter()
        .rposition(|&byte| byte == SEPARATOR)
        .map_or(0, |index| index + 1);
    OsStr::from_bytes(&bytes[start..])
}

fn components(path: &Path) -> Vec<&[u8]> {
    path.as_os_str()
        .as_bytes()
        .split(|&byte| byte == SEPARATOR)
        .filter(|part| !part.is_empty())
        .collect()
}

pub fn relpath(path: &Path, start: &Path, cwd: &Path) -> PathBuf {
    let path = abspath(path, cwd);
    let start = abspath(start, cwd);
    let path = components(&path);
    let start = components(&start);
    let common = path
        .iter()
        .zip(start.iter())
        .take_while(|(a, b)| a == b)
        .count();
    let mut parts: Vec<&[u8]> = vec![b".."; start.len() - common];
    parts.extend(&path[common..]);
    if parts.is_empty() {
        return PathBuf::from(".");
    }
    PathBuf::from(OsString::from_vec(parts.join(&SEPARATOR)))
}

pub fn dirname(path: &Path) -> PathBuf {
    let bytes = path.as_os_str().as_bytes();
    let end = bytes
        .iter()
        .rposition(|&byte| byte == SEPARATOR)
        .map_or(0, |index| index + 1);
    let head = &bytes[..end];
    let trimmed = head.len()
        - head
            .iter()
            .rev()
            .take_while(|&&byte| byte == SEPARATOR)
            .count();
    let head = if trimmed == 0 { head } else { &head[..trimmed] };
    PathBuf::from(OsStr::from_bytes(head))
}

pub fn commonpath(paths: &[PathBuf]) -> PathBuf {
    let first = components(&paths[0]);
    let mut common = first.len();
    for path in &paths[1..] {
        let parts = components(path);
        common = common.min(
            first
                .iter()
                .zip(parts.iter())
                .take_while(|(a, b)| a == b)
                .count(),
        );
    }
    let mut out = b"/".to_vec();
    out.extend(first[..common].join(&SEPARATOR));
    PathBuf::from(OsString::from_vec(out))
}

pub fn splitext(name: &str) -> (&str, &str) {
    let leading = name.len() - name.trim_start_matches('.').len();
    match name[leading..].rfind('.') {
        Some(index) => name.split_at(leading + index),
        None => (name, ""),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paths_are_normalised_as_posixpath_does() {
        for (path, expected) in [
            ("", "."),
            ("/", "/"),
            ("//", "//"),
            ("///a//b/", "/a/b"),
            ("//a/./b/../c", "//a/c"),
            ("a/../..", ".."),
            ("../a/../../b", "../../b"),
            ("/../a", "/a"),
            ("a/b/..", "a"),
            ("./", "."),
        ] {
            assert_eq!(normpath(Path::new(path)), PathBuf::from(expected), "{path}");
        }
        assert_eq!(
            abspath(Path::new("x/../y"), Path::new("/w")),
            PathBuf::from("/w/y")
        );
        assert_eq!(
            basename(Path::new("/a/b/__init__.py")),
            OsStr::new("__init__.py")
        );
        assert_eq!(basename(Path::new("/a/b/")), OsStr::new(""));
        let cwd = Path::new("/w");
        assert_eq!(
            relpath(Path::new("/r/a/b.py"), Path::new("/r"), cwd),
            PathBuf::from("a/b.py")
        );
        assert_eq!(
            relpath(Path::new("/x/y"), Path::new("/r/s"), cwd),
            PathBuf::from("../../x/y")
        );
        assert_eq!(
            relpath(Path::new("/r"), Path::new("/r"), cwd),
            PathBuf::from(".")
        );
        assert_eq!(dirname(Path::new("/a/b/c.py")), PathBuf::from("/a/b"));
        assert_eq!(dirname(Path::new("/c.py")), PathBuf::from("/"));
        assert_eq!(dirname(Path::new("c.py")), PathBuf::from(""));
        let paths = [
            PathBuf::from("/a/b/c"),
            PathBuf::from("/a/b/d"),
            PathBuf::from("/a/bx"),
        ];
        assert_eq!(commonpath(&paths), PathBuf::from("/a"));
        assert_eq!(commonpath(&[PathBuf::from("/")]), PathBuf::from("/"));
        assert_eq!(splitext("a.b.py"), ("a.b", ".py"));
        assert_eq!(splitext(".bashrc"), (".bashrc", ""));
        assert_eq!(splitext("..a.b"), ("..a", ".b"));
        assert_eq!(splitext("name"), ("name", ""));
    }
}
