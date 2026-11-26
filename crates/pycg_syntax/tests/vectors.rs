use pycg_syntax::parse::parse_source;
use pycg_syntax::read::read_source;
use pycg_syntax::tree::{position, walk};
use ruff_source_file::LineIndex;

const READING: &str = include_str!("vectors/reading.txt");
const POSITIONS: &str = include_str!("vectors/positions.txt");

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
