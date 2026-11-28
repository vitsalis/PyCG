use crate::arguments::{DESCRIPTION, OPTIONALS, Optional, POSITIONAL, POSITIONAL_HELP};
use crate::text::length;

const USAGE_PREFIX: &[u8] = b"usage: ";
const INDENT_STEP: i64 = 2;
const HELP_POSITION_MAX: i64 = 24;
const HELP_POSITION_MARGIN: i64 = 20;
const TEXT_WIDTH_MIN: i64 = 11;
const LONG_PROGRAM_NUMERATOR: i64 = 3;
const LONG_PROGRAM_DENOMINATOR: i64 = 4;

struct Part {
    text: Vec<u8>,
    length: i64,
}

impl Part {
    fn ascii(text: String) -> Part {
        assert!(text.is_ascii());
        let length = i64::try_from(text.len()).expect("a short part");
        Part {
            text: text.into_bytes(),
            length,
        }
    }
}

fn optional_usage(optional: Optional) -> Part {
    let string = optional.strings()[0];
    Part::ascii(match optional.metavar() {
        None => format!("[{string}]"),
        Some(metavar) => format!("[{string} {metavar}]"),
    })
}

fn spaces(count: i64) -> Vec<u8> {
    vec![b' '; usize::try_from(count).expect("a count of spaces")]
}

fn joined(parts: &[&Part]) -> Vec<u8> {
    let texts: Vec<&[u8]> = parts.iter().map(|part| part.text.as_slice()).collect();
    texts.join(&b' ')
}

fn lines_of(parts: &[&Part], indent: i64, prefix: Option<i64>, text_width: i64) -> Vec<Vec<u8>> {
    let mut lines = Vec::new();
    let mut line: Vec<&Part> = Vec::new();
    let mut line_length = prefix.unwrap_or(indent) - 1;
    for part in parts {
        if line_length + 1 + part.length > text_width && !line.is_empty() {
            lines.push([spaces(indent), joined(&line)].concat());
            line.clear();
            line_length = indent - 1;
        }
        line.push(part);
        line_length += part.length + 1;
    }
    if !line.is_empty() {
        lines.push([spaces(indent), joined(&line)].concat());
    }
    if prefix.is_some() {
        let first = lines.first_mut().expect("a first line");
        first.drain(..usize::try_from(indent).expect("an indent"));
    }
    lines
}

fn wrapped_usage(
    program: &Part,
    optionals: &[&Part],
    positionals: &[&Part],
    width: i64,
) -> Vec<u8> {
    let prefix_length = i64::try_from(USAGE_PREFIX.len()).expect("a short prefix");
    let short = i128::from(LONG_PROGRAM_DENOMINATOR) * i128::from(prefix_length + program.length)
        <= i128::from(LONG_PROGRAM_NUMERATOR) * i128::from(width);
    let lines = if short {
        let indent = prefix_length + program.length + 1;
        assert!(!optionals.is_empty());
        let first: Vec<&Part> = [&[program], optionals].concat();
        let mut lines = lines_of(&first, indent, Some(prefix_length), width);
        lines.extend(lines_of(positionals, indent, None, width));
        lines
    } else {
        let indent = prefix_length;
        let parts: Vec<&Part> = [optionals, positionals].concat();
        let mut lines = lines_of(&parts, indent, None, width);
        if lines.len() > 1 {
            lines = lines_of(optionals, indent, None, width);
            lines.extend(lines_of(positionals, indent, None, width));
        }
        lines.insert(0, program.text.clone());
        lines
    };
    lines.join(&b'\n')
}

fn format_usage(program: &[u8], width: i64) -> Vec<u8> {
    let program = Part {
        text: program.to_vec(),
        length: length(program),
    };
    let optionals: Vec<Part> = OPTIONALS
        .iter()
        .map(|&optional| optional_usage(optional))
        .collect();
    let positionals = [Part::ascii(format!("[{POSITIONAL} ...]"))];
    let optionals: Vec<&Part> = optionals.iter().collect();
    let positionals: Vec<&Part> = positionals.iter().collect();
    let all: Vec<&Part> = [&[&program], optionals.as_slice(), positionals.as_slice()].concat();
    let present: Vec<&Part> = all
        .into_iter()
        .filter(|part| !part.text.is_empty())
        .collect();
    let usage = joined(&present);
    let prefix_length = i64::try_from(USAGE_PREFIX.len()).expect("a short prefix");
    let usage_length = length(&usage);
    let usage = if prefix_length + usage_length > width {
        wrapped_usage(&program, &optionals, &positionals, width)
    } else {
        usage
    };
    [USAGE_PREFIX, &usage, b"\n\n"].concat()
}

fn finish(text: Vec<u8>) -> Vec<u8> {
    let mut collapsed = Vec::with_capacity(text.len());
    let mut newlines = 0;
    for byte in text {
        newlines = if byte == b'\n' { newlines + 1 } else { 0 };
        if newlines <= 2 {
            collapsed.push(byte);
        }
    }
    let start = collapsed.iter().position(|byte| *byte != b'\n');
    let end = collapsed.iter().rposition(|byte| *byte != b'\n');
    let mut out = match (start, end) {
        (Some(start), Some(end)) => collapsed[start..=end].to_vec(),
        _ => Vec::new(),
    };
    out.push(b'\n');
    out
}

pub fn usage(program: &[u8], width: i64) -> Vec<u8> {
    finish(format_usage(program, width))
}

fn wrap(text: &str, width: i64) -> Vec<String> {
    assert!(text.is_ascii());
    assert!(!text.contains('-'));
    assert!(!text.contains("  "));
    assert_eq!(text, text.trim());
    assert!(text.chars().all(|c| c == ' ' || !c.is_ascii_whitespace()));
    let width = usize::try_from(width).expect("a positive width");
    assert!(width >= 1);
    let mut chunks: Vec<&str> = text.split_inclusive(' ').flat_map(split_space).collect();
    chunks.reverse();
    let mut lines: Vec<String> = Vec::new();
    while !chunks.is_empty() {
        let mut line: Vec<&str> = Vec::new();
        let mut line_length = 0;
        if chunks.last() == Some(&" ") && !lines.is_empty() {
            chunks.pop();
        }
        while let Some(&chunk) = chunks.last()
            && line_length + chunk.len() <= width
        {
            line_length += chunk.len();
            line.push(chunk);
            chunks.pop();
        }
        if let Some(&chunk) = chunks.last()
            && chunk.len() > width
        {
            let space_left = width - line_length;
            if space_left > 0 {
                let (head, tail) = chunk.split_at(space_left);
                line.push(head);
                *chunks.last_mut().expect("the long chunk") = tail;
            }
        }
        if line.last() == Some(&" ") {
            line.pop();
        }
        if !line.is_empty() {
            lines.push(line.concat());
        }
    }
    lines
}

fn split_space(piece: &str) -> Vec<&str> {
    match piece.strip_suffix(' ') {
        Some(word) => vec![word, " "],
        None => vec![piece],
    }
}

struct Entry {
    invocation: String,
    help: String,
}

fn optional_entry(optional: Optional) -> Entry {
    let strings = optional.strings().join(", ");
    let invocation = match optional.metavar() {
        None => strings,
        Some(metavar) => format!("{strings} {metavar}"),
    };
    Entry {
        invocation,
        help: optional.help(),
    }
}

fn format_entry(entry: &Entry, help_position: i64, width: i64) -> Vec<u8> {
    let indent = INDENT_STEP;
    let help_width = (width - help_position).max(TEXT_WIDTH_MIN);
    let action_width = help_position - indent - 2;
    let invocation_length = i64::try_from(entry.invocation.len()).expect("a short invocation");
    let mut out = String::new();
    out.push_str(&" ".repeat(usize::try_from(indent).expect("an indent")));
    let indent_first = if invocation_length <= action_width {
        let padded = usize::try_from(action_width).expect("an action width");
        out.push_str(&format!("{:<padded$}  ", entry.invocation));
        0
    } else {
        out.push_str(&entry.invocation);
        out.push('\n');
        help_position
    };
    let lines = wrap(&entry.help, help_width);
    for (index, line) in lines.iter().enumerate() {
        let indent = if index == 0 {
            indent_first
        } else {
            help_position
        };
        out.push_str(&" ".repeat(usize::try_from(indent).expect("an indent")));
        out.push_str(line);
        out.push('\n');
    }
    out.into_bytes()
}

fn section(heading: &str, entries: &[Entry], help_position: i64, width: i64) -> Vec<u8> {
    let mut out = format!("\n{heading}:\n").into_bytes();
    for entry in entries {
        out.extend(format_entry(entry, help_position, width));
    }
    out.push(b'\n');
    out
}

pub fn help(program: &[u8], width: i64) -> Vec<u8> {
    let positionals = [Entry {
        invocation: POSITIONAL.to_owned(),
        help: POSITIONAL_HELP.to_owned(),
    }];
    let optionals: Vec<Entry> = OPTIONALS
        .iter()
        .map(|&optional| optional_entry(optional))
        .collect();
    let invocation_max = positionals
        .iter()
        .chain(&optionals)
        .map(|entry| i64::try_from(entry.invocation.len()).expect("a short invocation"))
        .max()
        .expect("an entry");
    let action_max_length = invocation_max + INDENT_STEP;
    let help_position_max =
        HELP_POSITION_MAX.min((width - HELP_POSITION_MARGIN).max(2 * INDENT_STEP));
    let help_position = (action_max_length + 2).min(help_position_max);
    let description = wrap(DESCRIPTION, width.max(TEXT_WIDTH_MIN)).join("\n");
    let text = [
        format_usage(program, width),
        format!("{description}\n\n").into_bytes(),
        section("positional arguments", &positionals, help_position, width),
        section("options", &optionals, help_position, width),
    ]
    .concat();
    finish(text)
}
