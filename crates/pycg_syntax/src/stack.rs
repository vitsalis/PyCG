#[cfg(unix)]
pub use unix::on_stack;
#[cfg(windows)]
pub use windows::on_stack;

#[cfg(unix)]
mod unix {
    use std::any::Any;
    use std::ffi::c_void;
    use std::panic::{AssertUnwindSafe, catch_unwind, resume_unwind};

    #[cfg(not(target_vendor = "apple"))]
    use libc::pthread_attr_setstack;

    #[cfg(target_vendor = "apple")]
    unsafe extern "C" {
        fn pthread_attr_setstack(
            attributes: *mut libc::pthread_attr_t,
            stack: *mut c_void,
            bytes: libc::size_t,
        ) -> libc::c_int;
    }

    type Outcome<R> = Result<R, Box<dyn Any + Send>>;

    struct Job<W, R> {
        work: Option<W>,
        outcome: Option<Outcome<R>>,
    }

    extern "C" fn run_job<W: FnOnce() -> R, R>(job: *mut c_void) -> *mut c_void {
        let job = unsafe { &mut *job.cast::<Job<W, R>>() };
        let work = job.work.take().expect("a job runs once");
        job.outcome = Some(catch_unwind(AssertUnwindSafe(work)));
        std::ptr::null_mut()
    }

    struct Reservation {
        base: *mut c_void,
        bytes: usize,
    }

    impl Reservation {
        fn new(bytes: usize) -> Reservation {
            let base = unsafe {
                libc::mmap(
                    std::ptr::null_mut(),
                    bytes,
                    libc::PROT_READ | libc::PROT_WRITE,
                    libc::MAP_PRIVATE | libc::MAP_ANONYMOUS | libc::MAP_NORESERVE,
                    -1,
                    0,
                )
            };
            assert_ne!(
                base,
                libc::MAP_FAILED,
                "a stack of {bytes} bytes is reserved"
            );
            let reservation = Reservation { base, bytes };
            let guarded = unsafe { libc::mprotect(base, page_bytes(), libc::PROT_NONE) };
            assert_eq!(guarded, 0, "the lowest page of the stack guards it");
            reservation
        }
    }

    impl Drop for Reservation {
        fn drop(&mut self) {
            let unmapped = unsafe { libc::munmap(self.base, self.bytes) };
            assert_eq!(unmapped, 0, "the stack is released");
        }
    }

    fn page_bytes() -> usize {
        let bytes = unsafe { libc::sysconf(libc::_SC_PAGESIZE) };
        usize::try_from(bytes).expect("the page size is positive")
    }

    pub fn on_stack<W, R>(bytes: usize, work: W) -> R
    where
        W: FnOnce() -> R + Send,
        R: Send,
    {
        let page = page_bytes();
        let bytes = bytes.div_ceil(page) * page + page;
        let reservation = Reservation::new(bytes);
        let mut job = Job {
            work: Some(work),
            outcome: None,
        };
        unsafe {
            let mut attributes = std::mem::zeroed::<libc::pthread_attr_t>();
            assert_eq!(
                libc::pthread_attr_init(&mut attributes),
                0,
                "thread attributes"
            );
            let stack = reservation.base.cast::<u8>().add(page).cast::<c_void>();
            assert_eq!(
                pthread_attr_setstack(&mut attributes, stack, bytes - page),
                0,
                "the thread runs on the reserved stack"
            );
            let mut thread = std::mem::zeroed::<libc::pthread_t>();
            let job_address = std::ptr::from_mut(&mut job).cast::<c_void>();
            assert_eq!(
                libc::pthread_create(&mut thread, &attributes, run_job::<W, R>, job_address),
                0,
                "the thread starts"
            );
            assert_eq!(
                libc::pthread_join(thread, std::ptr::null_mut()),
                0,
                "the thread ends"
            );
            assert_eq!(
                libc::pthread_attr_destroy(&mut attributes),
                0,
                "thread attributes"
            );
        }
        drop(reservation);
        match job.outcome.expect("the job ran") {
            Ok(result) => result,
            Err(panic) => resume_unwind(panic),
        }
    }
}

#[cfg(windows)]
mod windows {
    use std::panic::resume_unwind;

    pub fn on_stack<W, R>(bytes: usize, work: W) -> R
    where
        W: FnOnce() -> R + Send,
        R: Send,
    {
        std::thread::scope(|scope| {
            std::thread::Builder::new()
                .stack_size(bytes)
                .spawn_scoped(scope, work)
                .expect("the thread starts")
                .join()
                .unwrap_or_else(|panic| resume_unwind(panic))
        })
    }
}
