pub mod builder;
pub mod engine;
pub mod model;
pub mod models;
pub mod program;

use std::ffi::OsString;
use std::fmt;

use num_bigint::BigUint;

pub const CAP_DEFAULT_OBJECTS: u32 = 5000;

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Cap {
    Objects(BigUint),
    Unbounded,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Request {
    pub entry_points: Vec<OsString>,
    pub package: Option<OsString>,
    pub cap: Cap,
}

pub enum Analysis {}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    NotPorted,
}

impl fmt::Display for Error {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::NotPorted => formatter.write_str("the analysis is not ported yet"),
        }
    }
}

pub fn analyse(request: &Request) -> Result<Analysis, Error> {
    if let Cap::Objects(objects) = &request.cap {
        assert!(objects.bits() > 0);
    }
    Err(Error::NotPorted)
}
