use std::{hint::black_box, time::Instant};

#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

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

    #[cfg(target_arch = "x86_64")]
    let avx2_available = is_x86_feature_detected!("avx2");
    #[cfg(not(target_arch = "x86_64"))]
    let avx2_available = false;

    #[cfg(target_arch = "x86_64")]
    if avx2_available {
        let mut avx2_once = input.clone();
        unsafe {
            avx2_xor_in_place(&mut avx2_once, &key_words, &sigma_words, &nonce_words);
        }
        assert_eq!(
            scalar_once, avx2_once,
            "AVX2 output differs from retained T6 scalar core"
        );
    }

    // Warm all available paths before timed rounds.
    for _ in 0..50 {
        let mut a = input.clone();
        scalar_xor_in_place(&mut a, &key_words, &sigma_words, &nonce_words);
        black_box(a);

        let mut b = input.clone();
        let mut cipher = Salsa20::new((&KEY).into(), (&NONCE).into());
        cipher.apply_keystream(&mut b);
        black_box(b);

        #[cfg(target_arch = "x86_64")]
        if avx2_available {
            let mut c = input.clone();
            unsafe {
                avx2_xor_in_place(&mut c, &key_words, &sigma_words, &nonce_words);
            }
            black_box(c);
        }
    }

    let mut scalar_samples = Vec::with_capacity(ROUNDS);
    let mut crate_samples = Vec::with_capacity(ROUNDS);
    let mut avx2_samples = Vec::with_capacity(ROUNDS);
    let mut buffer = vec![0u8; CHUNK_BYTES];

    for round in 0..ROUNDS {
        if round % 2 == 0 {
            scalar_samples.push(measure_scalar(&input, &mut buffer, &key_words, &sigma_words, &nonce_words));
            crate_samples.push(measure_crate(&input, &mut buffer));
            #[cfg(target_arch = "x86_64")]
            if avx2_available {
                avx2_samples.push(measure_avx2(&input, &mut buffer, &key_words, &sigma_words, &nonce_words));
            }
        } else {
            #[cfg(target_arch = "x86_64")]
            if avx2_available {
                avx2_samples.push(measure_avx2(&input, &mut buffer, &key_words, &sigma_words, &nonce_words));
            }
            crate_samples.push(measure_crate(&input, &mut buffer));
            scalar_samples.push(measure_scalar(&input, &mut buffer, &key_words, &sigma_words, &nonce_words));
        }
    }

    scalar_samples.sort_by(f64::total_cmp);
    crate_samples.sort_by(f64::total_cmp);
    avx2_samples.sort_by(f64::total_cmp);
    let scalar = scalar_samples[ROUNDS / 2];
    let rustcrypto = crate_samples[ROUNDS / 2];
    let mib = (CHUNK_BYTES * ITERATIONS) as f64 / (1024.0 * 1024.0);
    let scalar_mib_s = mib / scalar;
    let rustcrypto_mib_s = mib / rustcrypto;
    let speedup = rustcrypto_mib_s / scalar_mib_s;
    let (avx2_seconds, avx2_mib_s, avx2_speedup) = if avx2_available && !avx2_samples.is_empty() {
        let seconds = avx2_samples[ROUNDS / 2];
        let mib_s = mib / seconds;
        (seconds, mib_s, mib_s / scalar_mib_s)
    } else {
        (f64::NAN, f64::NAN, f64::NAN)
    };

    println!(
        "T6_SALSA20_BENCH chunk_bytes={} iterations={} rounds={} scalar_seconds={:.6} rustcrypto_seconds={:.6} avx2_seconds={:.6} scalar_mib_s={:.3} rustcrypto_mib_s={:.3} avx2_mib_s={:.3} rustcrypto_vs_scalar={:.3}x avx2_vs_scalar={:.3}x avx2_available={}",
        CHUNK_BYTES,
        ITERATIONS,
        ROUNDS,
        scalar,
        rustcrypto,
        avx2_seconds,
        scalar_mib_s,
        rustcrypto_mib_s,
        avx2_mib_s,
        speedup,
        avx2_speedup,
        avx2_available,
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

#[cfg(target_arch = "x86_64")]
fn measure_avx2(
    input: &[u8],
    buffer: &mut [u8],
    key_words: &[u32; 8],
    sigma_words: &[u32; 4],
    nonce_words: &[u32; 2],
) -> f64 {
    let start = Instant::now();
    for _ in 0..ITERATIONS {
        buffer.copy_from_slice(input);
        unsafe {
            avx2_xor_in_place(buffer, key_words, sigma_words, nonce_words);
        }
        black_box(&*buffer);
    }
    start.elapsed().as_secs_f64()
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_xor_in_place(
    data: &mut [u8],
    key_words: &[u32; 8],
    sigma_words: &[u32; 4],
    nonce_words: &[u32; 2],
) {
    let mut offset = 0usize;
    let mut counter = 0u64;

    while offset + 8 * 64 <= data.len() {
        avx2_xor_8_blocks(
            &mut data[offset..offset + 8 * 64],
            key_words,
            sigma_words,
            nonce_words,
            counter,
        );
        offset += 8 * 64;
        counter += 8;
    }

    while offset < data.len() {
        let key_stream = salsa20_block_words(
            key_words,
            nonce_words,
            sigma_words,
            counter,
        );
        let take = (data.len() - offset).min(64);
        for index in 0..take {
            data[offset + index] ^= key_stream[index];
        }
        offset += take;
        counter += 1;
    }
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_xor_8_blocks(
    data: &mut [u8],
    k: &[u32; 8],
    c: &[u32; 4],
    n: &[u32; 2],
    counter: u64,
) {
    debug_assert_eq!(data.len(), 8 * 64);

    let zero = _mm256_setzero_si256();
    let mut initial = [zero; 16];

    initial[0] = _mm256_set1_epi32(c[0] as i32);
    initial[1] = _mm256_set1_epi32(k[0] as i32);
    initial[2] = _mm256_set1_epi32(k[1] as i32);
    initial[3] = _mm256_set1_epi32(k[2] as i32);
    initial[4] = _mm256_set1_epi32(k[3] as i32);
    initial[5] = _mm256_set1_epi32(c[1] as i32);
    initial[6] = _mm256_set1_epi32(n[0] as i32);
    initial[7] = _mm256_set1_epi32(n[1] as i32);

    let counter_lo: [u32; 8] = std::array::from_fn(|lane| (counter + lane as u64) as u32);
    let counter_hi: [u32; 8] = std::array::from_fn(|lane| ((counter + lane as u64) >> 32) as u32);
    initial[8] = _mm256_loadu_si256(counter_lo.as_ptr() as *const __m256i);
    initial[9] = _mm256_loadu_si256(counter_hi.as_ptr() as *const __m256i);

    initial[10] = _mm256_set1_epi32(c[2] as i32);
    initial[11] = _mm256_set1_epi32(k[4] as i32);
    initial[12] = _mm256_set1_epi32(k[5] as i32);
    initial[13] = _mm256_set1_epi32(k[6] as i32);
    initial[14] = _mm256_set1_epi32(k[7] as i32);
    initial[15] = _mm256_set1_epi32(c[3] as i32);

    let mut x = initial;
    for _ in 0..10 {
        avx2_quarter_round(&mut x, 0, 4, 8, 12);
        avx2_quarter_round(&mut x, 5, 9, 13, 1);
        avx2_quarter_round(&mut x, 10, 14, 2, 6);
        avx2_quarter_round(&mut x, 15, 3, 7, 11);

        avx2_quarter_round(&mut x, 0, 1, 2, 3);
        avx2_quarter_round(&mut x, 5, 6, 7, 4);
        avx2_quarter_round(&mut x, 10, 11, 8, 9);
        avx2_quarter_round(&mut x, 15, 12, 13, 14);
    }

    let mut lanes = [[0u32; 8]; 16];
    for word in 0..16 {
        x[word] = _mm256_add_epi32(x[word], initial[word]);
        _mm256_storeu_si256(
            lanes[word].as_mut_ptr() as *mut __m256i,
            x[word],
        );
    }

    for lane in 0..8 {
        let block_base = lane * 64;
        for word in 0..16 {
            let byte_offset = block_base + word * 4;
            let ptr = data.as_mut_ptr().add(byte_offset) as *mut u32;
            let value = std::ptr::read_unaligned(ptr);
            std::ptr::write_unaligned(ptr, value ^ lanes[word][lane]);
        }
    }
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_quarter_round(
    x: &mut [__m256i; 16],
    a: usize,
    b: usize,
    c: usize,
    d: usize,
) {
    let mut va = x[a];
    let mut vb = x[b];
    let mut vc = x[c];
    let mut vd = x[d];

    vb = _mm256_xor_si256(vb, avx2_rotl7(_mm256_add_epi32(va, vd)));
    vc = _mm256_xor_si256(vc, avx2_rotl9(_mm256_add_epi32(vb, va)));
    vd = _mm256_xor_si256(vd, avx2_rotl13(_mm256_add_epi32(vc, vb)));
    va = _mm256_xor_si256(va, avx2_rotl18(_mm256_add_epi32(vd, vc)));

    x[a] = va;
    x[b] = vb;
    x[c] = vc;
    x[d] = vd;
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_rotl7(value: __m256i) -> __m256i {
    _mm256_or_si256(
        _mm256_slli_epi32::<7>(value),
        _mm256_srli_epi32::<25>(value),
    )
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_rotl9(value: __m256i) -> __m256i {
    _mm256_or_si256(
        _mm256_slli_epi32::<9>(value),
        _mm256_srli_epi32::<23>(value),
    )
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_rotl13(value: __m256i) -> __m256i {
    _mm256_or_si256(
        _mm256_slli_epi32::<13>(value),
        _mm256_srli_epi32::<19>(value),
    )
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn avx2_rotl18(value: __m256i) -> __m256i {
    _mm256_or_si256(
        _mm256_slli_epi32::<18>(value),
        _mm256_srli_epi32::<14>(value),
    )
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
