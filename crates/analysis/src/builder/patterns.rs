use pycg_solver::NodeId;
use pycg_syntax::constants::{self, Constant as SyntaxConstant};
use pycg_syntax::tree::Node;
use ruff_python_ast::{Expr, Operator};

use crate::builder::ModuleBuilder;
use crate::builder::calls::Analysis;
use crate::builder::format::parse;

const PERCENT: u32 = '%' as u32;
const OPEN_PARENTHESIS: u32 = '(' as u32;
const CLOSE_PARENTHESIS: u32 = ')' as u32;
const DOT: u32 = '.' as u32;
const STAR: u32 = '*' as u32;
const FLAGS: [char; 5] = ['-', '+', ' ', '#', '0'];
const LENGTH_MODIFIERS: [char; 3] = ['h', 'l', 'L'];
const CONVERSIONS: [char; 16] = [
    's', 'r', 'a', 'd', 'i', 'o', 'u', 'x', 'X', 'e', 'E', 'f', 'F', 'g', 'G', 'c',
];
const WIDTH_MAX: u128 = (1 << 63) - 1;
const PRECISION_MAX: u128 = (1 << 31) - 1;

type Part = Option<Vec<u32>>;

fn is_one_of(character: u32, set: &[char]) -> bool {
    set.iter().any(|&member| u32::from(member) == character)
}

fn digit(character: u32) -> Option<u128> {
    char::from_u32(character)
        .and_then(|character| character.to_digit(10))
        .filter(|_| character < 128)
        .map(u128::from)
}

pub(crate) fn percent_spans(text: &[u32]) -> Option<Vec<(usize, usize, bool)>> {
    let mut spans = Vec::new();
    let mut index = 0;
    let end = text.len();
    while let Some(offset) = text[index..].iter().position(|&c| c == PERCENT) {
        let start = index + offset;
        index = start + 1;
        if text.get(index) == Some(&PERCENT) {
            index += 1;
            spans.push((start, index, true));
            continue;
        }
        let mut keyed = false;
        if text.get(index) == Some(&OPEN_PARENTHESIS) {
            index += 1;
            let mut depth = 1;
            while index < end && depth > 0 {
                if text[index] == OPEN_PARENTHESIS {
                    depth += 1;
                } else if text[index] == CLOSE_PARENTHESIS {
                    depth -= 1;
                }
                index += 1;
            }
            if depth > 0 {
                return None;
            }
            keyed = true;
        }
        while index < end && is_one_of(text[index], &FLAGS) {
            index += 1;
        }
        let mut stars = 0;
        for (precision, maximum) in [(false, WIDTH_MAX), (true, PRECISION_MAX)] {
            if precision {
                if text.get(index) != Some(&DOT) {
                    break;
                }
                index += 1;
            }
            if text.get(index) == Some(&STAR) {
                stars += 1;
                index += 1;
                continue;
            }
            let mut value: u128 = 0;
            while index < end
                && let Some(digit) = digit(text[index])
            {
                value = value * 10 + digit;
                if value > maximum {
                    return None;
                }
                index += 1;
            }
        }
        if stars > 0 && keyed {
            return None;
        }
        if index < end && is_one_of(text[index], &LENGTH_MODIFIERS) {
            index += 1;
        }
        if index == end || !is_one_of(text[index], &CONVERSIONS) {
            return None;
        }
        index += 1;
        spans.push((start, index, false));
    }
    Some(spans)
}

fn percent_parts(text: &[u32]) -> Option<Vec<Part>> {
    let spans = percent_spans(text)?;
    if spans.iter().all(|&(_, _, escaped)| escaped) {
        return None;
    }
    let mut parts = Vec::new();
    let mut start = 0;
    for (begin, end, escaped) in spans {
        parts.push(Some(text[start..begin].to_vec()));
        parts.push(escaped.then(|| vec![PERCENT]));
        start = end;
    }
    parts.push(Some(text[start..].to_vec()));
    Some(parts)
}

fn format_parts(text: &[u32]) -> Option<Vec<Part>> {
    let mut parts = Vec::new();
    for item in parse(text)? {
        let has_field = item.has_field();
        parts.push(Some(item.literal));
        if has_field {
            parts.push(None);
        }
    }
    Some(parts)
}

fn str_literal(expression: &Expr, source: &str) -> Option<Vec<u32>> {
    match constants::literal(expression, source) {
        Some(SyntaxConstant::Str(text)) => Some(text.code_points().to_vec()),
        _ => None,
    }
}

fn is_constant(expression: &Expr) -> bool {
    matches!(
        expression,
        Expr::StringLiteral(_)
            | Expr::BytesLiteral(_)
            | Expr::NumberLiteral(_)
            | Expr::BooleanLiteral(_)
            | Expr::NoneLiteral(_)
            | Expr::EllipsisLiteral(_)
    )
}

fn fstring_parts(node: &Node<'_>, source: &str) -> Vec<Part> {
    node.children()
        .iter()
        .map(|value| match value {
            Node::StringPiece(piece) => Some(
                constants::text_value(&piece.texts, source)
                    .code_points()
                    .to_vec(),
            ),
            _ => None,
        })
        .collect()
}

fn parts(node: &Node<'_>, source: &str) -> Option<Vec<Part>> {
    let expression = match node {
        Node::FormatSpec(..) => return Some(fstring_parts(node, source)),
        Node::Expr(expression) => *expression,
        _ => return None,
    };
    match expression {
        Expr::BinOp(operation) if operation.op == Operator::Add => {
            let mut items = Vec::new();
            let mut current = expression;
            while let Expr::BinOp(inner) = current
                && inner.op == Operator::Add
            {
                items.push(inner.right.as_ref());
                current = inner.left.as_ref();
            }
            items.push(current);
            let mut found = Vec::new();
            for item in items.into_iter().rev() {
                if is_constant(item) {
                    found.push(Some(str_literal(item, source)?));
                } else if let Expr::FString(_) = item {
                    found.extend(fstring_parts(&Node::Expr(item), source));
                } else {
                    found.push(None);
                }
            }
            Some(found)
        }
        Expr::BinOp(operation) if operation.op == Operator::Mod => {
            percent_parts(&str_literal(&operation.left, source)?)
        }
        Expr::FString(_) => Some(fstring_parts(node, source)),
        Expr::Call(call) => {
            let Expr::Attribute(method) = call.func.as_ref() else {
                return None;
            };
            if method.attr.as_str() != "format" || !matches!(*method.value, Expr::StringLiteral(_))
            {
                return None;
            }
            format_parts(&str_literal(&method.value, source)?)
        }
        _ => None,
    }
}

pub(crate) fn pattern_affixes(node: &Node<'_>, source: &str) -> Option<(Vec<u32>, Vec<u32>)> {
    let mut merged: Vec<Part> = Vec::new();
    for part in parts(node, source)? {
        match (part, merged.last_mut()) {
            (Some(text), Some(Some(last))) => last.extend(text),
            (part, _) => merged.push(part),
        }
    }
    let prefix = match merged.first() {
        Some(Some(_)) => merged.remove(0).expect("the first part is text"),
        _ => Vec::new(),
    };
    let suffix = match merged.last() {
        Some(Some(_)) => merged.pop().flatten().expect("the last part is text"),
        _ => Vec::new(),
    };
    if merged.is_empty() || (prefix.is_empty() && suffix.is_empty()) {
        return None;
    }
    Some((prefix, suffix))
}

impl<A: Analysis> ModuleBuilder<'_, '_, A> {
    pub(crate) fn string_pattern(&mut self, node: &Node<'_>) -> Option<NodeId> {
        let (prefix, suffix) = self.pattern_affixes(node)?;
        let pattern = self.analysis.pattern(&prefix, &suffix);
        Some(self.analysis.constant(pattern))
    }

    pub(crate) fn pattern_affixes(&self, node: &Node<'_>) -> Option<(Vec<u32>, Vec<u32>)> {
        pattern_affixes(node, self.source.text)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(value: &str) -> Vec<u32> {
        value.chars().map(u32::from).collect()
    }

    #[test]
    fn percent_formats_are_split_as_python_reads_them() {
        let parts = percent_parts(&text("a%(k)sb%%c%-5.2fd")).unwrap();
        assert_eq!(
            parts,
            vec![
                Some(text("a")),
                None,
                Some(text("b")),
                Some(text("%")),
                Some(text("c")),
                None,
                Some(text("d")),
            ]
        );
        assert_eq!(percent_parts(&text("100%%")), None);
        assert_eq!(percent_parts(&text("plain")), None);
        for rejected in [
            "%(k",
            "%(k)*d",
            "%q",
            "%",
            "%99999999999999999999d",
            "%.9999999999d",
        ] {
            assert_eq!(percent_spans(&text(rejected)), None, "{rejected}");
        }
    }

    #[test]
    fn format_strings_keep_their_literal_text() {
        assert_eq!(
            format_parts(&text("a{{b}}{x}c")).unwrap(),
            vec![
                Some(text("a{")),
                Some(text("b}")),
                Some(text("")),
                None,
                Some(text("c"))
            ]
        );
        assert_eq!(format_parts(&text("{")), None);
    }
}
