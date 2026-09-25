use std::{hint::black_box, time::Instant};

use salsa20::{
    cipher::{KeyIvInit, StreamCipher},
    Salsa20,
};

const CHUNK_BYTES: usize = 0x8000;
const ITERATIONS: usize = 2_000;
const ROUNDS: usize = 5;
const KEY: [u8; 32] = [
    0x64, 0x1d, 0x8a, 0x2f, 0xe3, 0x1d, 0x3a, 0xa6,
    0x36, 0x22, 0xbb, 0xc9, 0xce, 0x85, 0x87, 0x22,
    0x9d, 0x42, 0xb0, 0xf8, 0xed, 0x9b, 0x92, 0x41,
    0x30, 0xbf, 0x88, 0xb6, 0x5e, 0xdc, 0x50, 0xbe,
];
const SIGMA: [u8; 16] = *b"expand 32-byte k";
const NONCE: [u8; 8] = [0x41, 0x73, 0x32, 0x9b, 0x01, 0xaa, 0xf0, 0x7c];

fn main() {
    let mut input = vec![0u8; CHUNK_BYTES];
    for (i, byte) in input.iter_mut().enumerate() {
        *byte = ((i * 131 + 17) & 0xff) as u8;
    }

    let key_words = words8(&KEY);
    let sigma_words = words4(&SIGMA);
    let nonce_words = words2(&NONCE);

    let mut scalar_once = input.clone();
    scalar_xor_in_place(&mut scalar_once, &key_words, &sigma_words, &nonce_words);
    let mut crate_once = input.clone();
    let mut cipher = Salsa20::new((&KEY).into(), (&NONCE).into());
    cipher.apply_keystream(&mut crate_once);
    assert_eq!(scalar_once, crate_once, "RustCrypto output differs from retained T6 scalar core");

    // Warm both paths before timed rounds.
    for _ in 0..50 {
        let mut a = input.clone();
        scalar_xor_in_place(&mut a, &key_words, &sigma_words, &nonce_words);
        black_box(a);

        let mut b = input.clone();
        let mut cipher = Salsa20::new((&KEY).into(), (&NONCE).into());
        cipher.apply_keystream(&mut b);
        black_box(b);
    }

    let mut scalar_samples = Vec::with_capacity(ROUNDS);
    let mut crate_samples = Vec::with_capacity(ROUNDS);
    let mut buffer = vec![0u8; CHUNK_BYTES];

    for round in 0..ROUNDS {
        if round % 2 == 0 {
            scalar_samples.push(measure_scalar(&input, &mut buffer, &key_words, &sigma_words, &nonce_words));
            crate_samples.push(measure_crate(&input, &mut buffer));
        } else {
            crate_samples.push(measure_crate(&input, &mut buffer));
            scalar_samples.push(measure_scalar(&input, &mut buffer, &key_words, &sigma_words, &nonce_words));
        }
    }

    scalar_samples.sort_by(f64::total_cmp);
    crate_samples.sort_by(f64::total_cmp);
    let scalar = scalar_samples[ROUNDS / 2];
    let rustcrypto = crate_samples[ROUNDS / 2];
    let mib = (CHUNK_BYTES * ITERATIONS) as f64 / (1024.0 * 1024.0);
    let scalar_mib_s = mib / scalar;
    let rustcrypto_mib_s = mib / rustcrypto;
    let speedup = rustcrypto_mib_s / scalar_mib_s;

    println!(
        "T6_SALSA20_BENCH chunk_bytes={} iterations={} rounds={} scalar_seconds={:.6} rustcrypto_seconds={:.6} scalar_mib_s={:.3} rustcrypto_mib_s={:.3} rustcrypto_vs_scalar={:.3}x",
        CHUNK_BYTES,
        ITERATIONS,
        ROUNDS,
        scalar,
        rustcrypto,
        scalar_mib_s,
        rustcrypto_mib_s,
        speedup,
    );
}

fn measure_scalar(
    input: &[u8],
    buffer: &mut [u8],
    key_words: &[u32; 8],
    sigma_words: &[u32; 4],
    nonce_words: &[u32; 2],
) -> f64 {
    let start = Instant::now();
    for _ in 0..ITERATIONS {
        buffer.copy_from_slice(input);
        scalar_xor_in_place(buffer, key_words, sigma_words, nonce_words);
        black_box(&*buffer);
    }
    start.elapsed().as_secs_f64()
}

fn measure_crate(input: &[u8], buffer: &mut [u8]) -> f64 {
    let start = Instant::now();
    for _ in 0..ITERATIONS {
        buffer.copy_from_slice(input);
        let mut cipher = Salsa20::new((&KEY).into(), (&NONCE).into());
        cipher.apply_keystream(buffer);
        black_box(&*buffer);
    }
    start.elapsed().as_secs_f64()
}

fn scalar_xor_in_place(
    data: &mut [u8],
    key_words: &[u32; 8],
    sigma_words: &[u32; 4],
    nonce_words: &[u32; 2],
) {
    for (block_index, chunk) in data.chunks_mut(64).enumerate() {
        let key_stream = salsa20_block_words(
            key_words,
            nonce_words,
            sigma_words,
            block_index as u64,
        );
        for (value, key_byte) in chunk.iter_mut().zip(key_stream.iter()) {
            *value ^= *key_byte;
        }
    }
}

fn salsa20_block_words(
    k: &[u32; 8],
    n: &[u32; 2],
    c: &[u32; 4],
    counter: u64,
) -> [u8; 64] {
    let initial = [
        c[0], k[0], k[1], k[2], k[3], c[1], n[0], n[1],
        counter as u32, (counter >> 32) as u32, c[2], k[4],
        k[5], k[6], k[7], c[3],
    ];
    let mut x = initial;
    for _ in 0..10 {
        x[4] ^= x[0].wrapping_add(x[12]).rotate_left(7);
        x[8] ^= x[4].wrapping_add(x[0]).rotate_left(9);
        x[12] ^= x[8].wrapping_add(x[4]).rotate_left(13);
        x[0] ^= x[12].wrapping_add(x[8]).rotate_left(18);

        x[9] ^= x[5].wrapping_add(x[1]).rotate_left(7);
        x[13] ^= x[9].wrapping_add(x[5]).rotate_left(9);
        x[1] ^= x[13].wrapping_add(x[9]).rotate_left(13);
        x[5] ^= x[1].wrapping_add(x[13]).rotate_left(18);

        x[14] ^= x[10].wrapping_add(x[6]).rotate_left(7);
        x[2] ^= x[14].wrapping_add(x[10]).rotate_left(9);
        x[6] ^= x[2].wrapping_add(x[14]).rotate_left(13);
        x[10] ^= x[6].wrapping_add(x[2]).rotate_left(18);

        x[3] ^= x[15].wrapping_add(x[11]).rotate_left(7);
        x[7] ^= x[3].wrapping_add(x[15]).rotate_left(9);
        x[11] ^= x[7].wrapping_add(x[3]).rotate_left(13);
        x[15] ^= x[11].wrapping_add(x[7]).rotate_left(18);

        x[1] ^= x[0].wrapping_add(x[3]).rotate_left(7);
        x[2] ^= x[1].wrapping_add(x[0]).rotate_left(9);
        x[3] ^= x[2].wrapping_add(x[1]).rotate_left(13);
        x[0] ^= x[3].wrapping_add(x[2]).rotate_left(18);

        x[6] ^= x[5].wrapping_add(x[4]).rotate_left(7);
        x[7] ^= x[6].wrapping_add(x[5]).rotate_left(9);
        x[4] ^= x[7].wrapping_add(x[6]).rotate_left(13);
        x[5] ^= x[4].wrapping_add(x[7]).rotate_left(18);

        x[11] ^= x[10].wrapping_add(x[9]).rotate_left(7);
        x[8] ^= x[11].wrapping_add(x[10]).rotate_left(9);
        x[9] ^= x[8].wrapping_add(x[11]).rotate_left(13);
        x[10] ^= x[9].wrapping_add(x[8]).rotate_left(18);

        x[12] ^= x[15].wrapping_add(x[14]).rotate_left(7);
        x[13] ^= x[12].wrapping_add(x[15]).rotate_left(9);
        x[14] ^= x[13].wrapping_add(x[12]).rotate_left(13);
        x[15] ^= x[14].wrapping_add(x[13]).rotate_left(18);
    }

    let mut output = [0u8; 64];
    for index in 0..16 {
        output[index * 4..index * 4 + 4]
            .copy_from_slice(&x[index].wrapping_add(initial[index]).to_le_bytes());
    }
    output
}

fn words2(bytes: &[u8; 8]) -> [u32; 2] {
    [
        u32::from_le_bytes(bytes[0..4].try_into().unwrap()),
        u32::from_le_bytes(bytes[4..8].try_into().unwrap()),
    ]
}

fn words4(bytes: &[u8; 16]) -> [u32; 4] {
    std::array::from_fn(|index| {
        u32::from_le_bytes(bytes[index * 4..index * 4 + 4].try_into().unwrap())
    })
}

fn words8(bytes: &[u8; 32]) -> [u32; 8] {
    std::array::from_fn(|index| {
        u32::from_le_bytes(bytes[index * 4..index * 4 + 4].try_into().unwrap())
    })
}
