//! Builds the C telemetry library for the Rust binding and integration tests.

use std::env;

/// Compiles the platform-independent telemetry implementation with Cargo's
/// target-aware C compiler and archiver.
fn main() {
    println!("cargo:rerun-if-changed=c/telemetry.c");
    println!("cargo:rerun-if-changed=c/telemetry.h");

    let mut build = cc::Build::new();
    build
        .file("c/telemetry.c")
        .include("c")
        .warnings(true)
        .extra_warnings(true)
        .warnings_into_errors(true);

    if env::var("CARGO_CFG_TARGET_ENV").as_deref() != Ok("msvc") {
        build.std("c17");
    }

    build.compile("telemetry");
}
