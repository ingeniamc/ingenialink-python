//! Small release-mode benchmark for the native Rust data-type codecs.

use std::hint::black_box;
use std::time::Instant;

use _rust::data_type::{Bool, ByteArray512, F32, U64};

/// Number of operations per benchmark case.
const ITERATIONS: usize = 1_000_000;

/// Measures a no-argument benchmark operation and prints nanoseconds per call.
fn measure(label: &str, operation: impl Fn() -> u64) {
    let start = Instant::now();
    let mut result = 0_u64;
    for _ in 0..ITERATIONS {
        result ^= black_box(operation());
    }
    let nanos = start.elapsed().as_secs_f64() * 1_000_000_000.0 / ITERATIONS as f64;
    println!("{label:24} {nanos:8.2} ns/call ({result})");
}

fn main() {
    let integer_payload = [0xF0, 0xDE, 0xBC, 0x9A, 0x78, 0x56, 0x34, 0x12];
    let float_payload = [0x00, 0x00, 0x0A, 0x42];
    let byte_payload = [0xA5; 512];

    measure("U64 parse little", || {
        U64::parse(black_box(integer_payload)).unwrap_or_default()
    });
    measure("U64 parse big", || {
        U64::parse_be(black_box(integer_payload)).unwrap_or_default()
    });
    measure("U64 encode little", || {
        black_box(U64::encode(0x1234_5678_9ABC_DEF0))[0] as u64
    });
    measure("U64 encode big", || {
        black_box(U64::encode_be(0x1234_5678_9ABC_DEF0))[0] as u64
    });
    measure("F32 parse little", || {
        F32::parse(black_box(float_payload))
            .unwrap_or_default()
            .to_bits() as u64
    });
    measure("F32 parse big", || {
        F32::parse_be(black_box(float_payload))
            .unwrap_or_default()
            .to_bits() as u64
    });
    measure("Bool encode", || black_box(Bool::encode(true))[0] as u64);
    measure("ByteArray512 parse", || {
        black_box(ByteArray512::parse(black_box(byte_payload))).is_ok() as u64
    });
}
