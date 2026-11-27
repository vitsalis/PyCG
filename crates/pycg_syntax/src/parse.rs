use ruff_python_ast::token::{TokenKind, Tokens};
use ruff_python_ast::{Expr, ModModule, Operator, PythonVersion, UnaryOp};
use ruff_python_parser::{
    LexicalErrorType, Mode, ParseErrorType, ParseOptions, Parsed, parse_unchecked,
};
use ruff_source_file::LineIndex;
use ruff_text_size::{Ranged, TextSize};

use crate::tree::Node;

const TARGET_VERSION: PythonVersion = PythonVersion::PY314;
const PARENTHESES_DEPTH_MAX: usize = 200;
const INDENTATION_DEPTH_MAX: usize = 100;
const INTERPOLATED_STRING_DEPTH_MAX: usize = 149;
const STATEMENT_DEPTH_MAX: usize = 43_482;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SyntaxKind {
    Syntax,
    Indentation,
    Tab,
    Memory,
    Recursion,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ParseFailure {
    pub kind: SyntaxKind,
    pub line: Option<usize>,
}

impl ParseFailure {
    pub fn cause(&self) -> String {
        let name = match self.kind {
            SyntaxKind::Syntax => "SyntaxError",
            SyntaxKind::Indentation => "IndentationError",
            SyntaxKind::Tab => "TabError",
            SyntaxKind::Memory => "MemoryError",
            SyntaxKind::Recursion => "RecursionError",
        };
        match self.line {
            Some(line) => format!("{name} (line {line})"),
            None => name.to_owned(),
        }
    }
}

pub fn parse_source(source: &str) -> Result<Parsed<ModModule>, ParseFailure> {
    if source.contains('\0') {
        return Err(ParseFailure {
            kind: SyntaxKind::Syntax,
            line: None,
        });
    }
    let options = ParseOptions::from(Mode::Module).with_target_version(TARGET_VERSION);
    let parsed = parse_unchecked(source, options)
        .try_into_module()
        .expect("a module parse gives a module");
    let lines = LineIndex::from_source_text(source);
    let nesting = nesting(&parsed);
    if let Some(failure) = first_failure(&parsed, &lines, source, nesting.chain) {
        return Err(failure);
    }
    if nesting.depth > STATEMENT_DEPTH_MAX {
        return Err(ParseFailure {
            kind: SyntaxKind::Recursion,
            line: None,
        });
    }
    Ok(parsed)
}

fn first_failure(
    parsed: &Parsed<ModModule>,
    lines: &LineIndex,
    source: &str,
    chain: Option<TextSize>,
) -> Option<ParseFailure> {
    let line = |offset: TextSize| Some(lines.line_index(offset).get());
    let mut found: Vec<(TextSize, ParseFailure)> = Vec::new();
    if let Some(start) = tab_failure(parsed.tokens(), source) {
        found.push((
            start,
            ParseFailure {
                kind: SyntaxKind::Tab,
                line: line(start),
            },
        ));
    }
    if let Some((start, line_at, kind)) = bracket_failure(parsed.tokens()) {
        found.push((
            start,
            ParseFailure {
                kind,
                line: line(line_at),
            },
        ));
    }
    if let Some(start) = interpolated_string_failure(parsed.tokens()) {
        let failure = ParseFailure {
            kind: SyntaxKind::Syntax,
            line: line(start),
        };
        found.push((start, failure));
    }
    if let Some(start) = indentation_failure(parsed.tokens()) {
        let failure = ParseFailure {
            kind: SyntaxKind::Indentation,
            line: line(start),
        };
        found.push((start, failure));
    }
    if let Some(error) = parsed
        .errors()
        .iter()
        .min_by_key(|error| error.location.start())
    {
        let kind = error_kind(&error.error);
        let start = error.location.start();
        found.push((
            start,
            ParseFailure {
                kind,
                line: line(start),
            },
        ));
    }
    if let Some(start) = chain {
        let failure = ParseFailure {
            kind: SyntaxKind::Memory,
            line: None,
        };
        found.push((start, failure));
    }
    let unsupported = parsed.unsupported_syntax_errors().iter();
    if let Some(error) = unsupported.min_by_key(|error| error.range.start()) {
        let start = error.range.start();
        let failure = ParseFailure {
            kind: SyntaxKind::Syntax,
            line: line(start),
        };
        found.push((start, failure));
    }
    found
        .into_iter()
        .min_by_key(|(start, _)| *start)
        .map(|(_, failure)| failure)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Chain {
    Factor,
    Not,
    Conditional,
    Elif,
    Lambda,
    Power,
    Boolean,
}

impl Chain {
    fn of(node: &Node<'_>) -> Option<Chain> {
        match node {
            Node::Elif(_) => Some(Chain::Elif),
            Node::Expr(Expr::UnaryOp(unary)) if unary.op == UnaryOp::Not => Some(Chain::Not),
            Node::Expr(Expr::UnaryOp(_)) => Some(Chain::Factor),
            Node::Expr(Expr::If(_)) => Some(Chain::Conditional),
            Node::Expr(Expr::Lambda(_)) => Some(Chain::Lambda),
            Node::Expr(Expr::BinOp(binary)) if binary.op == Operator::Pow => Some(Chain::Power),
            Node::Expr(Expr::BoolOp(_)) => Some(Chain::Boolean),
            _ => None,
        }
    }

    fn length_max(self) -> usize {
        match self {
            Chain::Factor => 5_966,
            Chain::Not | Chain::Conditional => 5_967,
            Chain::Elif => 5_962,
            Chain::Lambda | Chain::Power => 2_983,
            Chain::Boolean => 199,
        }
    }
}

#[derive(Clone, Copy)]
struct Link {
    kind: Chain,
    length: usize,
}

struct Nesting {
    depth: usize,
    chain: Option<TextSize>,
}

fn nesting(parsed: &Parsed<ModModule>) -> Nesting {
    let tokens = parsed.tokens();
    let mut found = Nesting {
        depth: 0,
        chain: None,
    };
    let mut pending: Vec<(Node<'_>, usize, Option<Link>)> = parsed
        .syntax()
        .body
        .iter()
        .map(|statement| (Node::Stmt(statement), 1, None))
        .collect();
    while let Some((node, depth, outer)) = pending.pop() {
        found.depth = found.depth.max(depth);
        let chain = Chain::of(&node).map(|kind| match outer {
            Some(link) if link.kind == kind => Link {
                kind,
                length: link.length + 1,
            },
            _ => Link { kind, length: 1 },
        });
        if let Some(link) = chain
            && link.length > link.kind.length_max()
        {
            let start = node
                .range(tokens)
                .expect("a chained node has a position")
                .start();
            if found.chain.is_none_or(|earliest| start < earliest) {
                found.chain = Some(start);
            }
        }
        for child in node.children() {
            pending.push((child, depth + 1, chain));
        }
    }
    found
}

const EXPECTED_INDENTED_BLOCK: &str = "Expected an indented block";

fn error_kind(error: &ParseErrorType) -> SyntaxKind {
    match error {
        ParseErrorType::UnexpectedIndentation
        | ParseErrorType::Lexical(LexicalErrorType::IndentationError)
        | ParseErrorType::ExpectedToken {
            expected: TokenKind::Indent,
            ..
        } => SyntaxKind::Indentation,
        ParseErrorType::OtherError(message) if message.starts_with(EXPECTED_INDENTED_BLOCK) => {
            SyntaxKind::Indentation
        }
        _ => SyntaxKind::Syntax,
    }
}

fn closing(kind: TokenKind) -> Option<TokenKind> {
    match kind {
        TokenKind::Lpar => Some(TokenKind::Rpar),
        TokenKind::Lsqb => Some(TokenKind::Rsqb),
        TokenKind::Lbrace => Some(TokenKind::Rbrace),
        _ => None,
    }
}

fn bracket_failure(tokens: &Tokens) -> Option<(TextSize, TextSize, SyntaxKind)> {
    let mut open: Vec<(TokenKind, TextSize)> = Vec::new();
    for token in tokens {
        let kind = token.kind();
        if closing(kind).is_some() {
            if open.len() >= PARENTHESES_DEPTH_MAX {
                return Some((token.start(), token.start(), SyntaxKind::Syntax));
            }
            open.push((kind, token.start()));
        } else if matches!(kind, TokenKind::Rpar | TokenKind::Rsqb | TokenKind::Rbrace) {
            match open.pop() {
                Some((opener, _)) if closing(opener) == Some(kind) => {}
                _ => return Some((token.start(), token.start(), SyntaxKind::Syntax)),
            }
        }
    }
    open.last()
        .map(|&(_, start)| (start, start, SyntaxKind::Syntax))
}

fn interpolated_string_failure(tokens: &Tokens) -> Option<TextSize> {
    let mut depth = 0_usize;
    for token in tokens {
        match token.kind() {
            TokenKind::FStringStart | TokenKind::TStringStart => {
                if depth >= INTERPOLATED_STRING_DEPTH_MAX {
                    return Some(token.start());
                }
                depth += 1;
            }
            TokenKind::FStringEnd | TokenKind::TStringEnd => {
                depth = depth
                    .checked_sub(1)
                    .expect("an interpolated string ends after it starts");
            }
            _ => {}
        }
    }
    None
}

fn indentation_failure(tokens: &Tokens) -> Option<TextSize> {
    let mut indentation = 0_usize;
    for token in tokens {
        match token.kind() {
            TokenKind::Indent => {
                indentation += 1;
                if indentation >= INDENTATION_DEPTH_MAX {
                    return Some(token.start());
                }
            }
            TokenKind::Dedent => indentation = indentation.saturating_sub(1),
            _ => {}
        }
    }
    None
}

const TAB_SIZE: usize = 8;
const ALTERNATIVE_TAB_SIZE: usize = 1;

fn line_starts(tokens: &Tokens) -> Vec<TextSize> {
    let mut starts = Vec::new();
    let mut at_line_start = true;
    for token in tokens {
        match token.kind() {
            TokenKind::Newline => at_line_start = true,
            TokenKind::Indent | TokenKind::Dedent => {}
            TokenKind::NonLogicalNewline | TokenKind::Comment if at_line_start => {}
            TokenKind::EndOfFile => {}
            _ if at_line_start => {
                starts.push(token.start());
                at_line_start = false;
            }
            _ => {}
        }
    }
    starts
}

fn line_start(source: &str, offset: usize) -> usize {
    source[..offset]
        .rfind('\n')
        .map_or(0, |newline| newline + 1)
}

fn columns(source: &str, token_start: TextSize) -> (usize, usize) {
    let offset = usize::from(token_start);
    let line_start = line_start(source, offset);
    let (mut column, mut alternative) = (0, 0);
    for byte in source[line_start..].bytes() {
        match byte {
            b' ' => {
                column += 1;
                alternative += 1;
            }
            b'\t' => {
                column = (column / TAB_SIZE + 1) * TAB_SIZE;
                alternative = (alternative / ALTERNATIVE_TAB_SIZE + 1) * ALTERNATIVE_TAB_SIZE;
            }
            b'\x0c' => {
                column = 0;
                alternative = 0;
            }
            _ => break,
        }
    }
    (column, alternative)
}

fn tab_failure(tokens: &Tokens, source: &str) -> Option<TextSize> {
    let mut stack: Vec<(usize, usize)> = vec![(0, 0)];
    for token_start in line_starts(tokens) {
        let (column, alternative) = columns(source, token_start);
        let start = TextSize::try_from(line_start(source, usize::from(token_start)))
            .expect("a line start fits the source");
        let &(top, alternative_top) = stack.last().expect("the stack keeps its base");
        if column == top {
            if alternative != alternative_top {
                return Some(start);
            }
        } else if column > top {
            if alternative <= alternative_top {
                return Some(start);
            }
            stack.push((column, alternative));
        } else {
            while stack.len() > 1 && column < stack.last().expect("not empty").0 {
                stack.pop();
            }
            let &(top, alternative_top) = stack.last().expect("the stack keeps its base");
            if column == top && alternative != alternative_top {
                return Some(start);
            }
        }
    }
    None
}
