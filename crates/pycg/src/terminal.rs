use std::ffi::OsStr;

use num_bigint::BigInt;

use crate::integer::python_int;

const COLUMNS_FALLBACK: i64 = 80;
const WIDTH_MARGIN: i64 = 2;

pub fn width(columns_variable: Option<&OsStr>, terminal_columns: Option<i64>) -> i64 {
    let from_variable = columns_variable
        .and_then(|value| python_int(value.as_encoded_bytes()).ok())
        .filter(|columns| *columns > BigInt::ZERO)
        .map(|columns| i64::try_from(&columns).unwrap_or(i64::MAX));
    let columns = match from_variable {
        Some(columns) => columns,
        None => terminal_columns
            .filter(|columns| *columns != 0)
            .unwrap_or(COLUMNS_FALLBACK),
    };
    columns - WIDTH_MARGIN
}

#[cfg(unix)]
pub fn stdout_columns() -> Option<i64> {
    use std::ffi::c_int;

    #[cfg(all(target_os = "linux", target_env = "musl"))]
    type Request = c_int;
    #[cfg(not(all(target_os = "linux", target_env = "musl")))]
    type Request = std::ffi::c_ulong;

    #[cfg(all(
        target_os = "linux",
        any(target_arch = "x86_64", target_arch = "aarch64")
    ))]
    const GET_WINDOW_SIZE: Request = 0x5413;
    #[cfg(target_os = "macos")]
    const GET_WINDOW_SIZE: Request = 0x4008_7468;
    #[cfg(not(any(
        target_os = "macos",
        all(
            target_os = "linux",
            any(target_arch = "x86_64", target_arch = "aarch64")
        )
    )))]
    compile_error!("the request that reads the terminal size is not known for this platform");

    const STANDARD_OUTPUT: c_int = 1;

    #[repr(C)]
    struct WindowSize {
        rows: u16,
        columns: u16,
        width_pixels: u16,
        height_pixels: u16,
    }

    unsafe extern "C" {
        fn ioctl(descriptor: c_int, request: Request, ...) -> c_int;
    }

    let mut size = WindowSize {
        rows: 0,
        columns: 0,
        width_pixels: 0,
        height_pixels: 0,
    };
    let status = unsafe { ioctl(STANDARD_OUTPUT, GET_WINDOW_SIZE, &raw mut size) };
    (status == 0).then_some(i64::from(size.columns))
}

#[cfg(windows)]
pub fn stdout_columns() -> Option<i64> {
    use std::ffi::c_void;

    const STANDARD_OUTPUT_HANDLE: u32 = 0xffff_fff5;
    const INVALID_HANDLE: isize = -1;

    #[repr(C)]
    struct Coordinates {
        x: i16,
        y: i16,
    }

    #[repr(C)]
    struct Rectangle {
        left: i16,
        top: i16,
        right: i16,
        bottom: i16,
    }

    #[repr(C)]
    struct ScreenBufferInfo {
        size: Coordinates,
        cursor: Coordinates,
        attributes: u16,
        window: Rectangle,
        window_size_max: Coordinates,
    }

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetStdHandle(handle: u32) -> *mut c_void;
        fn GetConsoleScreenBufferInfo(console: *mut c_void, info: *mut ScreenBufferInfo) -> i32;
    }

    let handle = unsafe { GetStdHandle(STANDARD_OUTPUT_HANDLE) };
    if handle.is_null() || handle as isize == INVALID_HANDLE {
        return None;
    }
    let mut info = ScreenBufferInfo {
        size: Coordinates { x: 0, y: 0 },
        cursor: Coordinates { x: 0, y: 0 },
        attributes: 0,
        window: Rectangle {
            left: 0,
            top: 0,
            right: 0,
            bottom: 0,
        },
        window_size_max: Coordinates { x: 0, y: 0 },
    };
    let status = unsafe { GetConsoleScreenBufferInfo(handle, &raw mut info) };
    (status != 0).then(|| i64::from(info.window.right) - i64::from(info.window.left) + 1)
}
