use std::sync::OnceLock;

use rustc_hash::FxHashMap;

const DATA: &str = include_str!("../data/codecs.txt");
const BYTE_VALUES: usize = 256;
const NORMAL_NAME_CHARS_MAX: usize = 12;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decoding {
    Utf8,
    Utf8Sig,
    Ascii,
    Latin1,
    Charmap,
    Unsupported,
}

#[derive(Debug)]
pub struct Codec {
    pub module: String,
    pub decoding: Decoding,
    pub table: Option<Vec<Option<char>>>,
}

struct Registry {
    aliases: FxHashMap<String, String>,
    codecs: FxHashMap<String, Codec>,
}

fn registry() -> &'static Registry {
    static REGISTRY: OnceLock<Registry> = OnceLock::new();
    REGISTRY.get_or_init(|| parse_data(DATA))
}

fn parse_data(data: &str) -> Registry {
    let mut aliases = FxHashMap::default();
    let mut codecs: FxHashMap<String, Codec> = FxHashMap::default();
    for line in data.lines() {
        let mut words = line.split(' ');
        let word = words.next();
        match word {
            Some("python") => {}
            Some("alias") => {
                let alias = words.next().expect("an alias names itself");
                let module = words.next().expect("an alias names its module");
                aliases.insert(alias.to_owned(), module.to_owned());
            }
            Some("module") => {
                let module = words.next().expect("a module line names it");
                let decoding = decoding_of(words.next().expect("a module line says how"));
                let codec = Codec {
                    module: module.to_owned(),
                    decoding,
                    table: None,
                };
                codecs.insert(module.to_owned(), codec);
            }
            Some("table") => {
                let module = words.next().expect("a table names its module");
                let table: Vec<Option<char>> = words.map(table_entry).collect();
                assert_eq!(table.len(), BYTE_VALUES, "table of {module}");
                let codec = codecs.get_mut(module).expect("a table follows its module");
                assert_eq!(codec.decoding, Decoding::Charmap, "table of {module}");
                codec.table = Some(table);
            }
            _ => panic!("codec data line {line:?}"),
        }
    }
    Registry { aliases, codecs }
}

fn decoding_of(how: &str) -> Decoding {
    match how {
        "utf-8" => Decoding::Utf8,
        "utf-8-sig" => Decoding::Utf8Sig,
        "ascii" => Decoding::Ascii,
        "latin-1" => Decoding::Latin1,
        "charmap" => Decoding::Charmap,
        "unsupported" => Decoding::Unsupported,
        _ => panic!("codec decoding {how:?}"),
    }
}

fn table_entry(word: &str) -> Option<char> {
    if word == "-" {
        return None;
    }
    let point = u32::from_str_radix(word, 16).expect("a table entry is hexadecimal");
    Some(char::from_u32(point).expect("a table entry is a code point"))
}

pub fn normal_name(original: &str) -> String {
    let prefix: String = original.chars().take(NORMAL_NAME_CHARS_MAX).collect();
    let name = prefix.to_lowercase().replace('_', "-");
    if name == "utf-8" || name.starts_with("utf-8-") {
        return "utf-8".to_owned();
    }
    let latin = ["latin-1", "iso-8859-1", "iso-latin-1"];
    if latin.contains(&name.as_str()) || latin.iter().any(|l| name.starts_with(&format!("{l}-"))) {
        return "iso-8859-1".to_owned();
    }
    original.to_owned()
}

fn normalize_encoding(encoding: &str) -> String {
    let mut normal = String::new();
    let mut punctuation = false;
    for character in encoding.chars() {
        if character.is_alphanumeric() || character == '.' {
            if punctuation && !normal.is_empty() {
                normal.push('_');
            }
            if character.is_ascii() {
                normal.push(character);
            }
            punctuation = false;
        } else {
            punctuation = true;
        }
    }
    normal
}

pub fn lookup(encoding: &str) -> Option<&'static Codec> {
    let registry = registry();
    let normal = normalize_encoding(&encoding.to_ascii_lowercase());
    let aliased = registry
        .aliases
        .get(&normal)
        .or_else(|| registry.aliases.get(&normal.replace('.', "_")));
    let mut modules = Vec::new();
    if let Some(alias) = aliased {
        modules.push(alias.clone());
    }
    modules.push(normal);
    modules
        .iter()
        .filter(|module| !module.is_empty() && !module.contains('.'))
        .find_map(|module| registry.codecs.get(module))
}
