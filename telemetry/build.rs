//! Builds the C telemetry library for the Rust binding and integration tests.

use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    let output_dir = PathBuf::from(env::var_os("OUT_DIR").expect("Cargo must provide OUT_DIR"));
    let telemetry_object_file = output_dir.join("telemetry.o");
    let library_file = output_dir.join("libtelemetry.a");

    println!("cargo:rerun-if-changed=c/telemetry.c");
    println!("cargo:rerun-if-changed=c/telemetry.h");

    let compile_status = Command::new("cc")
        .args(["-std=c17", "-Wall", "-Wextra", "-Werror", "-Wpedantic"])
        .args(["-I", "c", "-c", "c/telemetry.c", "-o"])
        .arg(&telemetry_object_file)
        .status()
        .expect("failed to execute the C compiler");
    assert!(
        compile_status.success(),
        "the C compiler rejected telemetry.c"
    );

    let archive_status = Command::new("ar")
        .args(["crus"])
        .arg(&library_file)
        .arg(telemetry_object_file.as_os_str())
        .status()
        .expect("failed to execute the archive tool");
    assert!(
        archive_status.success(),
        "the archive tool rejected telemetry.o"
    );

    println!("cargo:rustc-link-search=native={}", output_dir.display());
    println!("cargo:rustc-link-lib=static=telemetry");
}
