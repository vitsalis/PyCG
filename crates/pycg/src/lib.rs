mod arguments;
mod help;
mod integer;
mod json;
mod terminal;
mod text;
mod unicode;
mod view;

use std::ffi::OsStr;

pub use arguments::{Options, Outcome, ViewOptions, parse, view_program};
pub use terminal::{stdout_columns, width};
pub use text::{code_points, for_stderr};
pub use view::{ViewError, view};

#[cfg(windows)]
const PATH_SEPARATORS: &[u8] = b"/\\";
#[cfg(not(windows))]
const PATH_SEPARATORS: &[u8] = b"/";

pub fn program_name(argument: &OsStr) -> Vec<u8> {
    let bytes = argument.as_encoded_bytes();
    let start = bytes
        .iter()
        .rposition(|byte| PATH_SEPARATORS.contains(byte))
        .map_or(0, |index| index + 1);
    bytes[start..].to_vec()
}
