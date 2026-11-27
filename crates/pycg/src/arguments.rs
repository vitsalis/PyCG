use std::ffi::OsString;

use num_bigint::{BigInt, Sign};
use pycg_analysis::{CAP_DEFAULT_OBJECTS, Cap, Request};

use crate::help;
use crate::integer::{IntError, python_int};
use crate::text::{Unit, decimal, first_unit_length, repr, units};

pub const DESCRIPTION: &str = "Write the call graph of a Python package as one JSON document.";
pub const POSITIONAL: &str = "entry_point";
pub const POSITIONAL_HELP: &str = "Entry points to be processed";

const PREFIX: u8 = b'-';
const SEPARATOR: &[u8] = b"--";
const ARGUMENT: u8 = b'A';
const OPTION: u8 = b'O';
const CAP_NONE: &[u8] = b"none";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Optional {
    Help,
    Package,
    PackageName,
    PackageVersion,
    Output,
    Cap,
}

pub const OPTIONALS: [Optional; 6] = [
    Optional::Help,
    Optional::Package,
    Optional::PackageName,
    Optional::PackageVersion,
    Optional::Output,
    Optional::Cap,
];

impl Optional {
    pub fn strings(self) -> &'static [&'static str] {
        match self {
            Optional::Help => &["-h", "--help"],
            Optional::Package => &["--package"],
            Optional::PackageName => &["--package-name"],
            Optional::PackageVersion => &["--package-version"],
            Optional::Output => &["-o", "--output"],
            Optional::Cap => &["--cap"],
        }
    }

    pub fn metavar(self) -> Option<&'static str> {
        match self {
            Optional::Help => None,
            Optional::Package => Some("PACKAGE"),
            Optional::PackageName => Some("PACKAGE_NAME"),
            Optional::PackageVersion => Some("PACKAGE_VERSION"),
            Optional::Output => Some("OUTPUT"),
            Optional::Cap => Some("N"),
        }
    }

    pub fn help(self) -> String {
        match self {
            Optional::Help => "show this help message and exit".to_owned(),
            Optional::Package => concat!(
                "Package root: module names are relative to it and only modules ",
                "under it are analysed. Default: the deepest directory that ",
                "contains every entry point"
            )
            .to_owned(),
            Optional::PackageName => "Name of the analysed package".to_owned(),
            Optional::PackageVersion => "Version of the analysed package".to_owned(),
            Optional::Output => "Output path".to_owned(),
            Optional::Cap => format!(
                concat!(
                    "The most objects that the analysis keeps for one variable or ",
                    "expression: past it the value is treated as unknown, and calls ",
                    "through it are reported as unresolved (saturated). 'none' ",
                    "removes the cap: the analysis may then not finish, or run out ",
                    "of memory, on large inputs. Default: {}"
                ),
                CAP_DEFAULT_OBJECTS
            ),
        }
    }

    fn name(self) -> String {
        self.strings().join("/")
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Options {
    pub request: Request,
    pub package_name: Option<OsString>,
    pub package_version: Option<OsString>,
    pub output: Option<OsString>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Outcome {
    Run(Options),
    Help(Vec<u8>),
    Usage(Vec<u8>),
}

enum Stop {
    Help,
    Error(Vec<u8>),
}

#[derive(Clone, Copy)]
struct Explicit<'a> {
    equals: bool,
    value: &'a [u8],
}

#[derive(Clone, Copy)]
struct Match<'a> {
    optional: Option<Optional>,
    string: &'a [u8],
    explicit: Option<Explicit<'a>>,
}

fn option_strings() -> impl Iterator<Item = (&'static [u8], Optional)> {
    OPTIONALS.into_iter().flat_map(|optional| {
        optional
            .strings()
            .iter()
            .map(move |string| (string.as_bytes(), optional))
    })
}

fn exact(string: &[u8]) -> Option<(&'static [u8], Optional)> {
    option_strings().find(|(candidate, _)| *candidate == string)
}

fn partition(argument: &[u8]) -> (&[u8], Option<&[u8]>) {
    match argument.iter().position(|byte| *byte == b'=') {
        None => (argument, None),
        Some(index) => (&argument[..index], Some(&argument[index + 1..])),
    }
}

fn concatenated(pieces: &[&[u8]]) -> Vec<u8> {
    pieces.concat()
}

fn argument_error(optional: Optional, message: &[u8]) -> Stop {
    let name = optional.name();
    Stop::Error(concatenated(&[
        b"argument ",
        name.as_bytes(),
        b": ",
        message,
    ]))
}

fn option_tuples(argument: &[u8]) -> Vec<Match<'_>> {
    assert!(argument.len() >= 2);
    assert_eq!(argument[0], PREFIX);
    let (prefix, value) = partition(argument);
    let explicit = value.map(|value| Explicit {
        equals: true,
        value,
    });
    let mut found = Vec::new();
    if argument[1] == PREFIX {
        for (string, optional) in option_strings() {
            if string.starts_with(prefix) {
                found.push(Match {
                    optional: Some(optional),
                    string,
                    explicit,
                });
            }
        }
        return found;
    }
    let short_length = 1 + first_unit_length(&argument[1..]);
    let (short, short_value) = argument.split_at(short_length);
    for (string, optional) in option_strings() {
        if string == short {
            found.push(Match {
                optional: Some(optional),
                string,
                explicit: Some(Explicit {
                    equals: false,
                    value: short_value,
                }),
            });
        } else if string.starts_with(prefix) {
            found.push(Match {
                optional: Some(optional),
                string,
                explicit,
            });
        }
    }
    found
}

fn looks_negative(argument: &[u8]) -> bool {
    let Some(rest) = argument.strip_prefix(&[PREFIX]) else {
        return false;
    };
    let rest = rest.strip_prefix(b".").unwrap_or(rest);
    matches!(units(rest).next(), Some(Unit::Char(character)) if decimal(character).is_some())
}

fn optional_matches(argument: &[u8]) -> Option<Vec<Match<'_>>> {
    if argument.first() != Some(&PREFIX) {
        return None;
    }
    if let Some((string, optional)) = exact(argument) {
        return Some(vec![Match {
            optional: Some(optional),
            string,
            explicit: None,
        }]);
    }
    if argument.len() == 1 {
        return None;
    }
    if let (string, Some(value)) = partition(argument)
        && let Some((string, optional)) = exact(string)
    {
        return Some(vec![Match {
            optional: Some(optional),
            string,
            explicit: Some(Explicit {
                equals: true,
                value,
            }),
        }]);
    }
    let found = option_tuples(argument);
    if !found.is_empty() {
        return Some(found);
    }
    if looks_negative(argument) || argument.contains(&b' ') {
        return None;
    }
    Some(vec![Match {
        optional: None,
        string: argument,
        explicit: None,
    }])
}

fn parse_cap(text: &[u8]) -> Result<Cap, Vec<u8>> {
    if text == CAP_NONE {
        return Ok(Cap::Unbounded);
    }
    let is_decimal = !text.is_empty()
        && units(text).all(|unit| matches!(unit, Unit::Char(c) if decimal(c).is_some()));
    if is_decimal {
        match python_int(text) {
            Ok(value) if value.sign() == Sign::Plus => {
                let objects = value.to_biguint().expect("a positive integer");
                return Ok(Cap::Objects(objects));
            }
            Ok(value) => assert_eq!(value, BigInt::ZERO),
            Err(IntError::DigitsPastLimit) => {
                return Err(format!("invalid parse_cap value: {}", repr(text)).into_bytes());
            }
            Err(IntError::Invalid) => panic!("decimal digits that int() rejects"),
        }
    }
    Err(format!("{} is not a positive integer or none", repr(text)).into_bytes())
}

#[cfg(unix)]
fn os_string(bytes: &[u8]) -> OsString {
    use std::os::unix::ffi::OsStrExt;
    std::ffi::OsStr::from_bytes(bytes).to_os_string()
}

#[cfg(not(unix))]
fn os_string(bytes: &[u8]) -> OsString {
    unsafe { OsString::from_encoded_bytes_unchecked(bytes.to_vec()) }
}

struct Parser<'a> {
    arguments: Vec<&'a [u8]>,
    pattern: Vec<u8>,
    matches: Vec<Option<Vec<Match<'a>>>>,
    positional_consumed: bool,
    extras: Vec<Vec<u8>>,
    entry_points: Vec<OsString>,
    package: Option<OsString>,
    package_name: Option<OsString>,
    package_version: Option<OsString>,
    output: Option<OsString>,
    cap: Cap,
}

impl<'a> Parser<'a> {
    fn new(arguments: Vec<&'a [u8]>) -> Parser<'a> {
        let mut pattern = Vec::with_capacity(arguments.len());
        let mut matches = Vec::with_capacity(arguments.len());
        let mut separated = false;
        for argument in &arguments {
            if separated {
                pattern.push(ARGUMENT);
                matches.push(None);
            } else if *argument == SEPARATOR {
                separated = true;
                pattern.push(PREFIX);
                matches.push(None);
            } else {
                let found = optional_matches(argument);
                pattern.push(if found.is_some() { OPTION } else { ARGUMENT });
                matches.push(found);
            }
        }
        Parser {
            arguments,
            pattern,
            matches,
            positional_consumed: false,
            extras: Vec::new(),
            entry_points: Vec::new(),
            package: None,
            package_name: None,
            package_version: None,
            output: None,
            cap: Cap::Objects(CAP_DEFAULT_OBJECTS.into()),
        }
    }

    fn take(&mut self, optional: Optional, value: Option<&[u8]>) -> Result<(), Stop> {
        let Some(value) = value else {
            assert_eq!(optional, Optional::Help);
            return Err(Stop::Help);
        };
        let stored = Some(os_string(value));
        match optional {
            Optional::Help => unreachable!("help stops the parse"),
            Optional::Package => self.package = stored,
            Optional::PackageName => self.package_name = stored,
            Optional::PackageVersion => self.package_version = stored,
            Optional::Output => self.output = stored,
            Optional::Cap => {
                self.cap =
                    parse_cap(value).map_err(|message| argument_error(optional, &message))?;
            }
        }
        Ok(())
    }

    fn consume_positionals(&mut self, start: usize) -> usize {
        if self.positional_consumed {
            return start;
        }
        let selected = &self.pattern[start..];
        let count = selected
            .iter()
            .take_while(|kind| **kind == ARGUMENT || **kind == PREFIX)
            .count();
        if count == 0 && selected.first() == Some(&OPTION) {
            return start;
        }
        let mut values = self.arguments[start..start + count].to_vec();
        if selected[..count].contains(&PREFIX) {
            let index = values
                .iter()
                .position(|value| *value == SEPARATOR)
                .expect("the separator among the values");
            values.remove(index);
        }
        self.entry_points = values.into_iter().map(os_string).collect();
        self.positional_consumed = true;
        start + count
    }

    fn consume_optional(&mut self, start: usize) -> Result<usize, Stop> {
        let found = self.matches[start].clone().expect("an option at the index");
        if found.len() > 1 {
            let strings: Vec<&[u8]> = found.iter().map(|each| each.string).collect();
            return Err(Stop::Error(concatenated(&[
                b"ambiguous option: ",
                self.arguments[start],
                b" could match ",
                &strings.join(&b", "[..]),
            ])));
        }
        let Match {
            optional,
            mut string,
            mut explicit,
        } = found[0];
        let Some(mut optional) = optional else {
            self.extras.push(self.arguments[start].to_vec());
            return Ok(start + 1);
        };
        let mut taken: Vec<(Optional, Option<&[u8]>)> = Vec::new();
        let mut unknown = None;
        let stop = loop {
            let takes_value = optional.metavar().is_some();
            let Some(Explicit { equals, value }) = explicit else {
                if !takes_value {
                    taken.push((optional, None));
                    break start + 1;
                }
                if self.pattern.get(start + 1) != Some(&ARGUMENT) {
                    return Err(argument_error(optional, b"expected one argument"));
                }
                taken.push((optional, Some(self.arguments[start + 1])));
                break start + 2;
            };
            if takes_value {
                taken.push((optional, Some(value)));
                break start + 1;
            }
            if string[1] == PREFIX || value.is_empty() || equals || value[0] == PREFIX {
                let message = format!("ignored explicit argument {}", repr(value));
                return Err(argument_error(optional, message.as_bytes()));
            }
            taken.push((optional, None));
            let (first, rest) = value.split_at(first_unit_length(value));
            let Some((next_string, next)) = exact(&concatenated(&[&[PREFIX], first])) else {
                unknown = Some(concatenated(&[&[PREFIX], value]));
                break start + 1;
            };
            optional = next;
            string = next_string;
            explicit = match rest.first() {
                None => None,
                Some(b'=') => Some(Explicit {
                    equals: true,
                    value: &rest[1..],
                }),
                Some(_) => Some(Explicit {
                    equals: false,
                    value: rest,
                }),
            };
        };
        for (optional, value) in taken {
            self.take(optional, value)?;
        }
        self.extras.extend(unknown);
        Ok(stop)
    }

    fn run(&mut self) -> Result<(), Stop> {
        let last_option = self.matches.iter().rposition(Option::is_some);
        let mut start = 0;
        if let Some(last_option) = last_option {
            while start <= last_option {
                let next_option = (start..=last_option)
                    .find(|index| self.matches[*index].is_some())
                    .expect("an option at or before the last");
                if start != next_option {
                    let end = self.consume_positionals(start);
                    if end > start {
                        start = end;
                        continue;
                    }
                }
                if self.matches[start].is_none() {
                    let skipped = &self.arguments[start..next_option];
                    self.extras
                        .extend(skipped.iter().map(|argument| argument.to_vec()));
                    start = next_option;
                }
                start = self.consume_optional(start)?;
            }
        }
        let stop = self.consume_positionals(start);
        let rest = &self.arguments[stop..];
        self.extras
            .extend(rest.iter().map(|argument| argument.to_vec()));
        if self.extras.is_empty() {
            return Ok(());
        }
        let joined = self.extras.join(&b' ');
        Err(Stop::Error(concatenated(&[
            b"unrecognized arguments: ",
            &joined,
        ])))
    }
}

pub fn parse(program: &[u8], arguments: &[OsString], width: i64) -> Outcome {
    let bytes: Vec<&[u8]> = arguments.iter().map(|a| a.as_encoded_bytes()).collect();
    let mut parser = Parser::new(bytes);
    match parser.run() {
        Ok(()) => Outcome::Run(Options {
            request: Request {
                entry_points: parser.entry_points,
                package: parser.package,
                cap: parser.cap,
            },
            package_name: parser.package_name,
            package_version: parser.package_version,
            output: parser.output,
        }),
        Err(Stop::Help) => Outcome::Help(help::help(program, width)),
        Err(Stop::Error(message)) => {
            let usage = help::usage(program, width);
            Outcome::Usage(concatenated(&[
                &usage,
                program,
                b": error: ",
                &message,
                b"\n",
            ]))
        }
    }
}
