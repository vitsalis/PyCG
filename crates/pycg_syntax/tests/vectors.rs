use pycg_syntax::constants::{Constant, literal, text_value};
use pycg_syntax::names::{is_identifier, nfkc};
use pycg_syntax::parse::parse_source;
use pycg_syntax::read::read_source;
use pycg_syntax::tree::{Node, position, walk};
use ruff_source_file::LineIndex;

const READING: &str = include_str!("vectors/reading.txt");
const POSITIONS: &str = include_str!("vectors/positions.txt");
const CONSTANTS: &str = include_str!("vectors/constants.txt");
const NAMES: &str = include_str!("vectors/names.txt");

fn hex(text: &str) -> Vec<u8> {
    assert_eq!(text.len() % 2, 0, "hex of whole bytes: {text}");
    (0..text.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&text[index..index + 2], 16).expect("hex digits"))
        .collect()
}

fn vector_lines(data: &str) -> impl Iterator<Item = &str> {
    let mut lines = data.lines();
    let version = lines
        .next()
        .expect("the vectors name the Python that wrote them");
    assert!(version.starts_with("python "), "{version}");
    lines
}

fn read_and_parse(bytes: &[u8]) -> (String, String) {
    let source = match read_source(bytes) {
        Ok(source) => source,
        Err(failure) => return ("failed".to_owned(), failure.cause()),
    };
    match parse_source(&source) {
        Ok(_) => {
            let text: String = source.bytes().map(|byte| format!("{byte:02x}")).collect();
            ("ok".to_owned(), text)
        }
        Err(failure) => ("failed".to_owned(), failure.cause()),
    }
}

#[test]
fn reading_and_parsing_give_what_python_gives() {
    let mut cases = 0;
    for line in vector_lines(READING) {
        let fields: Vec<&str> = line.split('\t').collect();
        let [name, input, status, value] = fields[..] else {
            panic!("reading vector {line:?}");
        };
        let found = read_and_parse(&hex(input));
        assert_eq!(found, (status.to_owned(), value.to_owned()), "case {name}");
        cases += 1;
    }
    assert!(cases > 0, "reading vectors");
}

fn dump(source: &str) -> Vec<String> {
    let parsed = parse_source(source).expect("a position vector parses");
    let lines = LineIndex::from_source_text(source);
    walk(parsed.syntax())
        .iter()
        .filter_map(|node| {
            let range = node.range(parsed.tokens())?;
            let at = position(range, &lines);
            let (line, column) = (at.lineno, at.col_offset);
            let (end_line, end_column) = (at.end_lineno, at.end_col_offset);
            Some(format!(
                "{} {line} {column} {end_line} {end_column}",
                node.kind()
            ))
        })
        .collect()
}

#[test]
fn positions_are_those_of_python_in_walk_order() {
    let mut lines = vector_lines(POSITIONS);
    let mut cases = 0;
    while let Some(header) = lines.next() {
        let words: Vec<&str> = header.split(' ').collect();
        let ["case", name, source] = words[..] else {
            panic!("position vector header {header:?}");
        };
        let source = String::from_utf8(hex(source)).expect("a vector source is UTF-8");
        let expected: Vec<String> = lines
            .by_ref()
            .take_while(|line| *line != "end")
            .map(str::to_owned)
            .collect();
        assert_eq!(dump(&source), expected, "case {name}");
        cases += 1;
    }
    assert!(cases > 0, "position vectors");
}

fn float_bits(value: f64) -> String {
    format!("{:016x}", value.to_bits())
}

fn constant_text(constant: &Constant) -> String {
    match constant {
        Constant::None => "None".to_owned(),
        Constant::Bool(value) => format!("Bool {}", if *value { "True" } else { "False" }),
        Constant::Ellipsis => "Ellipsis".to_owned(),
        Constant::Int(value) => format!("Int {value}"),
        Constant::Float(value) => format!("Float {}", float_bits(*value)),
        Constant::Complex { real, imag } => {
            format!("Complex {} {}", float_bits(*real), float_bits(*imag))
        }
        Constant::Str(value) => {
            let mut text = "Str".to_owned();
            for point in value.code_points() {
                text.push_str(&format!(" {point:x}"));
            }
            text
        }
        Constant::Bytes(value) => {
            let hex: String = value.iter().map(|byte| format!("{byte:02x}")).collect();
            format!("Bytes {hex}")
        }
    }
}

fn constants(source: &str) -> Vec<String> {
    let parsed = parse_source(source).expect("a constant vector parses");
    let mut found = Vec::new();
    for node in walk(parsed.syntax()) {
        let constant = match &node {
            Node::Expr(expression) => literal(expression, source),
            Node::StringPiece(piece) => Some(Constant::Str(text_value(&piece.texts, source))),
            _ => None,
        };
        if let Some(constant) = constant {
            found.push(constant_text(&constant));
        }
    }
    found
}

#[test]
fn constants_have_the_values_of_python() {
    let mut lines = vector_lines(CONSTANTS);
    let mut cases = 0;
    while let Some(header) = lines.next() {
        let words: Vec<&str> = header.split(' ').collect();
        let ["case", name, source] = words[..] else {
            panic!("constant vector header {header:?}");
        };
        let source = String::from_utf8(hex(source)).expect("a vector source is UTF-8");
        let expected: Vec<String> = lines
            .by_ref()
            .take_while(|line| *line != "end")
            .map(str::to_owned)
            .collect();
        assert_eq!(constants(&source), expected, "case {name}");
        cases += 1;
    }
    assert!(cases > 0, "constant vectors");
}

fn text_of(code_points: &str) -> String {
    if code_points == "-" {
        return String::new();
    }
    code_points
        .split(',')
        .map(|word| {
            let point = u32::from_str_radix(word, 16).expect("a code point is hexadecimal");
            char::from_u32(point).expect("a vector code point is a character")
        })
        .collect()
}

#[test]
fn names_are_normalised_and_tested_as_python_does() {
    let mut cases = 0;
    for line in vector_lines(NAMES) {
        let (kind, rest) = line.split_once(' ').expect("a name vector has a kind");
        match kind {
            "nfkc" => {
                let (input, output) = rest.split_once(' ').expect("an input and an output");
                assert_eq!(nfkc(&text_of(input)), text_of(output), "{line}");
            }
            "start" | "continue" => {
                let (point, expected) = rest.split_once(' ').expect("a point and an answer");
                let character = text_of(point);
                let text = if kind == "start" {
                    character
                } else {
                    format!("a{character}")
                };
                assert_eq!(
                    is_identifier(&text).to_string(),
                    expected.to_lowercase(),
                    "{line}"
                );
            }
            _ => panic!("name vector {line:?}"),
        }
        cases += 1;
    }
    assert!(cases > 0, "name vectors");
}
