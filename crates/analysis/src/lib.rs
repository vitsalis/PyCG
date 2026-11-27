pub mod builder;
pub mod engine;
pub mod model;
pub mod models;
pub mod program;
pub mod results;

use std::ffi::{OsStr, OsString};
use std::fmt;
use std::panic::{self, AssertUnwindSafe};
use std::path::{Path, PathBuf};

use num_bigint::{BigInt, BigUint};

use crate::engine::trace::Untraced;
use crate::engine::{Engine, NotPorted};
use crate::program::Program;
use crate::program::paths::PathsError;
use crate::results::AnalysisPart;

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

pub struct Analysed {
    pub program: Program<Engine<Untraced>>,
    pub results: AnalysisPart,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Error {
    NotPorted(String),
    Paths(String),
}

impl fmt::Display for Error {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::NotPorted(feature) => write!(formatter, "not ported: {feature}"),
            Error::Paths(message) => formatter.write_str(message),
        }
    }
}

pub fn analyse(
    request: &Request,
    cwd: &Path,
    warn: &mut dyn FnMut(&OsStr),
) -> Result<Analysed, Error> {
    let (cap, recorded) = match &request.cap {
        Cap::Objects(objects) => {
            assert!(objects.bits() > 0);
            (
                u32::try_from(objects).ok(),
                Some(BigInt::from(objects.clone())),
            )
        }
        Cap::Unbounded => (None, None),
    };
    let entry_points: Vec<PathBuf> = request.entry_points.iter().map(PathBuf::from).collect();
    let package = request.package.as_ref().map(PathBuf::from);
    let engine = Engine::new(cap, Untraced);
    let mut program = Program::new(&entry_points, package.as_deref(), cwd, engine)
        .map_err(|error| Error::Paths(error.to_string()))?;
    let solved = panic::catch_unwind(AssertUnwindSafe(|| {
        program.build_modules()?;
        program.analysis.solve();
        let modules: Vec<String> = program.modules.keys().cloned().collect();
        let mut results = program.analysis.results(&modules);
        if cap.is_some() {
            assert_eq!(results.cap, recorded);
        }
        results.cap = recorded.clone();
        Ok(results)
    }));
    for warning in &program.warnings {
        warn(warning);
    }
    match solved {
        Ok(results) => results
            .map(|results| Analysed { program, results })
            .map_err(|error: PathsError| Error::Paths(error.to_string())),
        Err(payload) => match payload.downcast::<NotPorted>() {
            Ok(not_ported) => Err(Error::NotPorted(not_ported.0)),
            Err(payload) => panic::resume_unwind(payload),
        },
    }
}
