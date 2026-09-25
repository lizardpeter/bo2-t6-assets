use std::{env, fs, hint::black_box, time::Instant};

use flate2::{Decompress, FlushDecompress, Status};
use sha1::{Digest as Sha1Digest, Sha1};
use sha2::{Digest as Sha2Digest, Sha256};

#[cfg(feature = "rustcrypto")]
use salsa20::{
    cipher::{KeyIvInit, StreamCipher},
    Salsa20,
};

const HEADER_SIZE: usize = 0x138;
const MAX_RECORD: usize = 0x8000;
const VANILLA_BUFFER_SIZE: usize = 0x80000;
const STREAM_COUNT: usize = 4;
const TABLE_ENTRIES: usize = 800;
const ENTRY_SIZE: usize = 20;
const TABLE_DWORDS: usize = TABLE_ENTRIES * (ENTRY_SIZE / 4);
const KEY: [u8; 32] = [
    0x64, 0x1d, 0x8a, 0x2f, 0xe3, 0x1d, 0x3a, 0xa6, 0x36, 0x22, 0xbb, 0xc9, 0xce, 0x85,
    0x87, 0x22, 0x9d, 0x42, 0xb0, 0xf8, 0xed, 0x9b, 0x92, 0x41, 0x30, 0xbf, 0x88, 0xb6,
    0x5e, 0xdc, 0x50, 0xbe,
];
const SIGMA: [u8; 16] = *b"expand 32-byte k";

fn main() {
    if let Err(error) = run() {
        eprintln!("t6-fastfile-perf: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let path = args.next().ok_or_else(|| "usage: t6-fastfile-perf <retail.ff> [iterations]".to_owned())?;
    let iterations = args
        .next()
        .map(|v| v.parse::<usize>().map_err(|e| format!("bad iterations: {e}")))
        .transpose()?
        .unwrap_or(5)
        .max(1);
    let ff = fs::read(path).map_err(|e| format!("read failed: {e}"))?;

    let warm = decode(&ff)?;
    black_box(&warm.output);
    let expected_sha = hex(Sha256::digest(&warm.output).as_slice());

    let start = Instant::now();
    let mut last = None;
    for _ in 0..iterations {
        let result = decode(black_box(&ff))?;
        if result.output.len() != warm.output.len() {
            return Err("decode length drift".to_owned());
        }
        #[cfg(not(feature = "nohash"))]
        if result.sha256 != expected_sha {
            return Err("decode hash identity drift".to_owned());
        }
        black_box(&result.output);
        last = Some(result);
    }
    let elapsed = start.elapsed().as_secs_f64();
    let last = last.unwrap();
    #[cfg(feature = "nohash")]
    {
        let actual = hex(Sha256::digest(&last.output).as_slice());
        if actual != expected_sha {
            return Err("untimed post-benchmark identity hash mismatch".to_owned());
        }
    }
    let encrypted_mib = ff.len() as f64 * iterations as f64 / 1048576.0;
    let expanded_mib = last.output.len() as f64 * iterations as f64 / 1048576.0;

    println!(
        "T6_PERF backend={} salsa={} iterations={} records={} encrypted_bytes={} expanded_bytes={} seconds={:.6} encrypted_mib_s={:.3} expanded_mib_s={:.3} expanded_sha256={}",
        backend_name(),
        salsa_name(),
        iterations,
        last.records,
        ff.len(),
        last.output.len(),
        elapsed,
        encrypted_mib / elapsed,
        expanded_mib / elapsed,
        last.sha256
    );
    Ok(())
}

struct DecodeResult {
    output: Vec<u8>,
    records: usize,
    sha256: String,
}

fn decode(ff: &[u8]) -> Result<DecodeResult, String> {
    #[cfg(feature = "streaming-parallel")]
    {
        return decode_parallel_streaming(ff);
    }
    #[cfg(all(not(feature = "streaming-parallel"), feature = "parallel"))]
    {
        return decode_parallel(ff);
    }
    #[cfg(all(not(feature = "streaming-parallel"), not(feature = "parallel")))]
    {
        decode_serial(ff)
    }
}

fn decode_serial(ff: &[u8]) -> Result<DecodeResult, String> {
    validate_header(ff)?;
    let zone = zone_name(ff)?;
    let mut table = initial_table(zone)?;
    let mut counters = [0usize; STREAM_COUNT];
    #[cfg(feature = "reserve")]
    let mut output = Vec::with_capacity(max_output_capacity(ff)?);
    #[cfg(not(feature = "reserve"))]
    let mut output = Vec::new();
    let mut plaintext = Vec::with_capacity(MAX_RECORD);
    let mut decompressed = vec![0u8; MAX_RECORD];
    let mut inflater = Decompress::new(false);
    let mut sha1 = Sha1::new();
    #[cfg(not(feature = "nohash"))]
    let mut sha256 = Sha256::new();

    #[cfg(feature = "scalar")]
    let key_words = words8(&KEY);
    #[cfg(feature = "scalar")]
    let sigma_words = words4(&SIGMA);

    let mut pos = HEADER_SIZE;
    let mut record = 0usize;
    while pos + 4 <= ff.len() {
        let raw_mod = pos % VANILLA_BUFFER_SIZE;
        if raw_mod + 4 > VANILLA_BUFFER_SIZE {
            pos += VANILLA_BUFFER_SIZE - raw_mod;
            if pos + 4 > ff.len() {
                break;
            }
        }
        let len_off = pos;
        let len = read_u32(ff, pos)? as usize;
        pos += 4;
        if len == 0 {
            if ff[len_off..].iter().any(|b| *b != 0) {
                return Err(format!("nonzero data after terminator at 0x{len_off:x}"));
            }
            break;
        }
        if len > MAX_RECORD {
            return Err(format!("record {record} length {len} exceeds {MAX_RECORD}"));
        }
        let end = pos.checked_add(len).ok_or_else(|| "record range overflow".to_owned())?;
        let ciphertext = ff.get(pos..end).ok_or_else(|| format!("record {record} truncated"))?;

        let stream = record % STREAM_COUNT;
        let counter = counters[stream];
        let table_index = (counter * STREAM_COUNT + stream) % TABLE_ENTRIES;
        let table_offset = table_index * ENTRY_SIZE;
        let nonce: [u8; 8] = table[table_offset..table_offset + 8]
            .try_into()
            .map_err(|_| "nonce slice".to_owned())?;

        plaintext.resize(len, 0);
        decrypt_into(
            ciphertext,
            &nonce,
            plaintext.as_mut_slice(),
            #[cfg(feature = "scalar")]
            &key_words,
            #[cfg(feature = "scalar")]
            &sigma_words,
        );

        let status = inflater
            .decompress(&plaintext, &mut decompressed, FlushDecompress::Finish)
            .map_err(|e| format!("record {record} inflate failed: {e}"))?;
        if status != Status::StreamEnd {
            return Err(format!("record {record} inflate status {status:?}"));
        }
        let expanded = inflater.total_out() as usize;
        let chunk = &decompressed[..expanded];
        output.extend_from_slice(chunk);
        #[cfg(not(feature = "nohash"))]
        sha256.update(chunk);
        inflater.reset(false);

        sha1.update(&plaintext);
        let digest = sha1.finalize_reset();
        let next = counter + 1;
        let next_index = (next * STREAM_COUNT + stream) % TABLE_ENTRIES;
        let next_offset = next_index * ENTRY_SIZE;
        for (i, byte) in digest.iter().enumerate() {
            table[next_offset + i] ^= byte;
        }
        counters[stream] = next;
        record += 1;
        pos = end;
    }

    #[cfg(feature = "encrypted-hash")]
    {
        black_box(Sha256::digest(ff));
    }

    #[cfg(not(feature = "nohash"))]
    let expanded_sha = hex(sha256.finalize().as_slice());
    #[cfg(feature = "nohash")]
    let expanded_sha = String::new();

    Ok(DecodeResult {
        output,
        records: record,
        sha256: expanded_sha,
    })
}

#[cfg(feature = "streaming-parallel")]
fn decode_parallel_streaming(ff: &[u8]) -> Result<DecodeResult, String> {
    use std::sync::mpsc::sync_channel;

    validate_header(ff)?;
    let zone = zone_name(ff)?;
    let records = scan_records_streaming(ff)?;
    let output_capacity = records
        .len()
        .checked_mul(MAX_RECORD)
        .ok_or_else(|| "streaming parallel output capacity overflow".to_owned())?;

    let output = std::thread::scope(|scope| -> Result<Vec<u8>, String> {
        let mut receivers = Vec::with_capacity(STREAM_COUNT);
        let mut handles = Vec::with_capacity(STREAM_COUNT);

        for stream in 0..STREAM_COUNT {
            // At most two decoded XChunks per stream may wait for the ordered
            // consumer. With 0x8000-byte records this bounds queued expanded
            // data to roughly 256 KiB across all four streams.
            let (sender, receiver) = sync_channel::<Result<Vec<u8>, String>>(2);
            receivers.push(receiver);
            let records_ref = &records;
            handles.push(scope.spawn(move || {
                decode_one_stream_streaming(ff, zone, records_ref, stream, sender)
            }));
        }

        let mut output = Vec::with_capacity(output_capacity);
        for record_index in 0..records.len() {
            let stream = record_index % STREAM_COUNT;
            let chunk = receivers[stream]
                .recv()
                .map_err(|_| format!(
                    "streaming parallel worker {stream} disconnected before record {record_index}"
                ))??;
            output.extend_from_slice(&chunk);
        }

        for (stream, handle) in handles.into_iter().enumerate() {
            handle
                .join()
                .map_err(|_| format!("streaming parallel worker {stream} panicked"))??;
        }

        Ok(output)
    })?;

    #[cfg(feature = "encrypted-hash")]
    {
        black_box(Sha256::digest(ff));
    }

    #[cfg(not(feature = "nohash"))]
    let expanded_sha = hex(Sha256::digest(&output).as_slice());
    #[cfg(feature = "nohash")]
    let expanded_sha = String::new();

    Ok(DecodeResult {
        output,
        records: records.len(),
        sha256: expanded_sha,
    })
}

#[cfg(feature = "streaming-parallel")]
fn decode_one_stream_streaming(
    ff: &[u8],
    zone: &[u8],
    records: &[EncryptedRecordStreaming],
    stream: usize,
    sender: std::sync::mpsc::SyncSender<Result<Vec<u8>, String>>,
) -> Result<(), String> {
    let mut table = initial_table(zone)?;
    let mut plaintext = Vec::with_capacity(MAX_RECORD);
    let mut decompressed = vec![0u8; MAX_RECORD];
    let mut inflater = Decompress::new(false);
    let mut sha1 = Sha1::new();
    let mut counter = 0usize;

    for record_index in (stream..records.len()).step_by(STREAM_COUNT) {
        let work = (|| -> Result<Vec<u8>, String> {
            let record = records[record_index];
            let ciphertext = ff
                .get(record.start..record.end)
                .ok_or_else(|| format!(
                    "streaming parallel record {record_index} ciphertext is truncated"
                ))?;

            let table_index = (counter * STREAM_COUNT + stream) % TABLE_ENTRIES;
            let table_offset = table_index * ENTRY_SIZE;
            let nonce: [u8; 8] = table[table_offset..table_offset + 8]
                .try_into()
                .map_err(|_| "streaming parallel nonce slice".to_owned())?;

            plaintext.resize(ciphertext.len(), 0);
            decrypt_into(ciphertext, &nonce, plaintext.as_mut_slice());

            let status = inflater
                .decompress(&plaintext, &mut decompressed, FlushDecompress::Finish)
                .map_err(|e| format!(
                    "streaming parallel record {record_index} inflate failed: {e}"
                ))?;
            if status != Status::StreamEnd {
                return Err(format!(
                    "streaming parallel record {record_index} inflate status {status:?}"
                ));
            }
            let expanded = inflater.total_out() as usize;
            if expanded > decompressed.len() {
                return Err(format!(
                    "streaming parallel record {record_index} inflated beyond buffer"
                ));
            }
            let chunk = decompressed[..expanded].to_vec();
            inflater.reset(false);

            sha1.update(&plaintext);
            let digest = sha1.finalize_reset();
            let next = counter + 1;
            let next_index = (next * STREAM_COUNT + stream) % TABLE_ENTRIES;
            let next_offset = next_index * ENTRY_SIZE;
            for (i, byte) in digest.iter().enumerate() {
                table[next_offset + i] ^= byte;
            }
            counter = next;

            Ok(chunk)
        })();

        match work {
            Ok(chunk) => sender
                .send(Ok(chunk))
                .map_err(|_| format!("streaming parallel consumer dropped stream {stream}"))?,
            Err(error) => {
                let _ = sender.send(Err(error.clone()));
                return Err(error);
            }
        }
    }

    Ok(())
}

#[cfg(feature = "streaming-parallel")]
#[derive(Clone, Copy)]
struct EncryptedRecordStreaming {
    start: usize,
    end: usize,
}

#[cfg(feature = "streaming-parallel")]
fn scan_records_streaming(ff: &[u8]) -> Result<Vec<EncryptedRecordStreaming>, String> {
    let mut records = Vec::new();
    let mut pos = HEADER_SIZE;

    while pos + 4 <= ff.len() {
        let raw_mod = pos % VANILLA_BUFFER_SIZE;
        if raw_mod + 4 > VANILLA_BUFFER_SIZE {
            pos += VANILLA_BUFFER_SIZE - raw_mod;
            if pos + 4 > ff.len() {
                break;
            }
        }

        let length_offset = pos;
        let len = read_u32(ff, pos)? as usize;
        pos += 4;
        if len == 0 {
            if ff[length_offset..].iter().any(|byte| *byte != 0) {
                return Err(format!(
                    "streaming parallel scan found nonzero bytes after terminator at 0x{length_offset:x}"
                ));
            }
            break;
        }
        if len > MAX_RECORD {
            return Err(format!(
                "streaming parallel record {} length {len} exceeds {MAX_RECORD}",
                records.len()
            ));
        }
        let end = pos
            .checked_add(len)
            .ok_or_else(|| "streaming parallel record range overflow".to_owned())?;
        if end > ff.len() {
            return Err(format!(
                "streaming parallel record {} escapes file",
                records.len()
            ));
        }
        records.push(EncryptedRecordStreaming { start: pos, end });
        pos = end;
    }

    if pos < ff.len() && ff[pos..].iter().any(|byte| *byte != 0) {
        return Err(format!(
            "streaming parallel scan found nonzero trailing bytes at 0x{pos:x}"
        ));
    }

    Ok(records)
}

#[cfg(feature = "parallel")]
#[derive(Clone, Copy)]
struct EncryptedRecord {
    start: usize,
    end: usize,
}

#[cfg(feature = "parallel")]
struct ParallelStream {
    bytes: Vec<u8>,
    lengths: Vec<usize>,
}

#[cfg(feature = "parallel")]
fn decode_parallel(ff: &[u8]) -> Result<DecodeResult, String> {
    validate_header(ff)?;
    let zone = zone_name(ff)?;
    let records = scan_records(ff)?;

    let streams = std::thread::scope(|scope| -> Result<Vec<ParallelStream>, String> {
        let mut handles = Vec::with_capacity(STREAM_COUNT);
        for stream in 0..STREAM_COUNT {
            let records_ref = &records;
            handles.push(scope.spawn(move || decode_one_stream(ff, zone, records_ref, stream)));
        }

        let mut decoded = Vec::with_capacity(STREAM_COUNT);
        for handle in handles {
            let result = handle
                .join()
                .map_err(|_| "parallel T6 stream worker panicked".to_owned())??;
            decoded.push(result);
        }
        Ok(decoded)
    })?;

    let total_output: usize = streams.iter().map(|stream| stream.bytes.len()).sum();
    let mut output = Vec::with_capacity(total_output);
    let mut offsets = [0usize; STREAM_COUNT];
    let mut local_indices = [0usize; STREAM_COUNT];

    for record_index in 0..records.len() {
        let stream = record_index % STREAM_COUNT;
        let local_index = local_indices[stream];
        let length = *streams[stream]
            .lengths
            .get(local_index)
            .ok_or_else(|| format!("parallel stream {stream} missing record {local_index} length"))?;
        let start = offsets[stream];
        let end = start
            .checked_add(length)
            .ok_or_else(|| "parallel output range overflow".to_owned())?;
        let chunk = streams[stream]
            .bytes
            .get(start..end)
            .ok_or_else(|| format!("parallel stream {stream} output is truncated"))?;
        output.extend_from_slice(chunk);
        offsets[stream] = end;
        local_indices[stream] += 1;
    }

    #[cfg(feature = "encrypted-hash")]
    {
        black_box(Sha256::digest(ff));
    }

    #[cfg(not(feature = "nohash"))]
    let expanded_sha = hex(Sha256::digest(&output).as_slice());
    #[cfg(feature = "nohash")]
    let expanded_sha = String::new();

    Ok(DecodeResult {
        output,
        records: records.len(),
        sha256: expanded_sha,
    })
}

#[cfg(feature = "parallel")]
fn decode_one_stream(
    ff: &[u8],
    zone: &[u8],
    records: &[EncryptedRecord],
    stream: usize,
) -> Result<ParallelStream, String> {
    let mut table = initial_table(zone)?;
    let local_count = (records.len() + STREAM_COUNT - 1 - stream) / STREAM_COUNT;
    let mut bytes = Vec::with_capacity(local_count.saturating_mul(MAX_RECORD));
    let mut lengths = Vec::with_capacity(local_count);
    let mut plaintext = Vec::with_capacity(MAX_RECORD);
    let mut decompressed = vec![0u8; MAX_RECORD];
    let mut inflater = Decompress::new(false);
    let mut sha1 = Sha1::new();
    let mut counter = 0usize;

    for record_index in (stream..records.len()).step_by(STREAM_COUNT) {
        let record = records[record_index];
        let ciphertext = ff
            .get(record.start..record.end)
            .ok_or_else(|| format!("parallel record {record_index} ciphertext is truncated"))?;

        let table_index = (counter * STREAM_COUNT + stream) % TABLE_ENTRIES;
        let table_offset = table_index * ENTRY_SIZE;
        let nonce: [u8; 8] = table[table_offset..table_offset + 8]
            .try_into()
            .map_err(|_| "parallel T6 nonce slice".to_owned())?;

        plaintext.resize(ciphertext.len(), 0);
        decrypt_into(ciphertext, &nonce, plaintext.as_mut_slice());

        let status = inflater
            .decompress(&plaintext, &mut decompressed, FlushDecompress::Finish)
            .map_err(|e| format!("parallel record {record_index} inflate failed: {e}"))?;
        if status != Status::StreamEnd {
            return Err(format!(
                "parallel record {record_index} inflate status {status:?}"
            ));
        }
        let expanded = inflater.total_out() as usize;
        if expanded > decompressed.len() {
            return Err(format!("parallel record {record_index} inflated beyond buffer"));
        }
        bytes.extend_from_slice(&decompressed[..expanded]);
        lengths.push(expanded);
        inflater.reset(false);

        sha1.update(&plaintext);
        let digest = sha1.finalize_reset();
        let next = counter + 1;
        let next_index = (next * STREAM_COUNT + stream) % TABLE_ENTRIES;
        let next_offset = next_index * ENTRY_SIZE;
        for (i, byte) in digest.iter().enumerate() {
            table[next_offset + i] ^= byte;
        }
        counter = next;
    }

    Ok(ParallelStream { bytes, lengths })
}

#[cfg(feature = "parallel")]
fn scan_records(ff: &[u8]) -> Result<Vec<EncryptedRecord>, String> {
    let mut records = Vec::new();
    let mut pos = HEADER_SIZE;

    while pos + 4 <= ff.len() {
        let raw_mod = pos % VANILLA_BUFFER_SIZE;
        if raw_mod + 4 > VANILLA_BUFFER_SIZE {
            pos += VANILLA_BUFFER_SIZE - raw_mod;
            if pos + 4 > ff.len() {
                break;
            }
        }

        let length_offset = pos;
        let len = read_u32(ff, pos)? as usize;
        pos += 4;
        if len == 0 {
            if ff[length_offset..].iter().any(|byte| *byte != 0) {
                return Err(format!(
                    "parallel scan found nonzero bytes after terminator at 0x{length_offset:x}"
                ));
            }
            break;
        }
        if len > MAX_RECORD {
            return Err(format!(
                "parallel scan record {} length {len} exceeds {MAX_RECORD}",
                records.len()
            ));
        }
        let end = pos
            .checked_add(len)
            .ok_or_else(|| "parallel record range overflow".to_owned())?;
        if end > ff.len() {
            return Err(format!("parallel scan record {} escapes file", records.len()));
        }
        records.push(EncryptedRecord { start: pos, end });
        pos = end;
    }

    if pos < ff.len() && ff[pos..].iter().any(|byte| *byte != 0) {
        return Err(format!("parallel scan found nonzero trailing bytes at 0x{pos:x}"));
    }

    Ok(records)
}

#[cfg(feature = "rustcrypto")]
fn decrypt_into(data: &[u8], nonce: &[u8; 8], output: &mut [u8]) {
    output.copy_from_slice(data);
    let mut cipher = Salsa20::new(&KEY.into(), &(*nonce).into());
    cipher.apply_keystream(output);
}

#[cfg(feature = "scalar")]
fn decrypt_into(
    data: &[u8],
    nonce: &[u8; 8],
    output: &mut [u8],
    key_words: &[u32; 8],
    sigma_words: &[u32; 4],
) {
    let nonce_words = words2(nonce);
    for (block_index, chunk) in data.chunks(64).enumerate() {
        let keystream = salsa20_block_words(key_words, &nonce_words, sigma_words, block_index as u64);
        let offset = block_index * 64;
        for (i, value) in chunk.iter().enumerate() {
            output[offset + i] = *value ^ keystream[i];
        }
    }
}

#[cfg(feature = "scalar")]
fn salsa20_block_words(k: &[u32; 8], n: &[u32; 2], c: &[u32; 4], counter: u64) -> [u8; 64] {
    let initial = [
        c[0], k[0], k[1], k[2], k[3], c[1], n[0], n[1],
        counter as u32, (counter >> 32) as u32, c[2], k[4], k[5], k[6], k[7], c[3],
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

    let mut out = [0u8; 64];
    for i in 0..16 {
        out[i * 4..i * 4 + 4].copy_from_slice(&x[i].wrapping_add(initial[i]).to_le_bytes());
    }
    out
}

#[cfg(feature = "reserve")]
fn max_output_capacity(ff: &[u8]) -> Result<usize, String> {
    let mut pos = HEADER_SIZE;
    let mut records = 0usize;
    while pos + 4 <= ff.len() {
        let raw_mod = pos % VANILLA_BUFFER_SIZE;
        if raw_mod + 4 > VANILLA_BUFFER_SIZE {
            pos += VANILLA_BUFFER_SIZE - raw_mod;
            if pos + 4 > ff.len() {
                break;
            }
        }
        let len = read_u32(ff, pos)? as usize;
        pos += 4;
        if len == 0 {
            break;
        }
        if len > MAX_RECORD {
            return Err(format!("pre-scan record {records} length {len} exceeds {MAX_RECORD}"));
        }
        pos = pos.checked_add(len).ok_or_else(|| "pre-scan range overflow".to_owned())?;
        if pos > ff.len() {
            return Err(format!("pre-scan record {records} escapes file"));
        }
        records = records.checked_add(1).ok_or_else(|| "pre-scan record count overflow".to_owned())?;
    }
    records
        .checked_mul(MAX_RECORD)
        .ok_or_else(|| "pre-scan output capacity overflow".to_owned())
}

fn validate_header(ff: &[u8]) -> Result<(), String> {
    if ff.len() < HEADER_SIZE || ff.get(..8) != Some(b"TAff0100") || read_u32(ff, 8)? != 0x93 {
        return Err("unsupported T6 FastFile header".to_owned());
    }
    if ff.get(12..20) != Some(b"PHEEBs71") {
        return Err("missing PHEEBs71".to_owned());
    }
    Ok(())
}

fn zone_name(ff: &[u8]) -> Result<&[u8], String> {
    let field = ff.get(24..56).ok_or_else(|| "zone field truncated".to_owned())?;
    let end = field.iter().position(|b| *b == 0).unwrap_or(field.len());
    if end == 0 || !field[..end].is_ascii() {
        return Err("invalid zone name".to_owned());
    }
    Ok(&field[..end])
}

fn initial_table(zone: &[u8]) -> Result<Vec<u8>, String> {
    if zone.is_empty() {
        return Err("empty zone".to_owned());
    }
    let mut table = vec![0u8; TABLE_ENTRIES * ENTRY_SIZE];
    for dword_index in 0..TABLE_DWORDS {
        let value = zone[dword_index % zone.len()];
        let offset = dword_index * 4;
        table[offset..offset + 4].fill(value);
    }
    Ok(table)
}

fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, String> {
    let raw: [u8; 4] = bytes
        .get(offset..offset + 4)
        .ok_or_else(|| format!("truncated u32 at 0x{offset:x}"))?
        .try_into()
        .map_err(|_| "u32 slice".to_owned())?;
    Ok(u32::from_le_bytes(raw))
}

#[cfg(feature = "scalar")]
fn words2(bytes: &[u8; 8]) -> [u32; 2] {
    [
        u32::from_le_bytes(bytes[0..4].try_into().unwrap()),
        u32::from_le_bytes(bytes[4..8].try_into().unwrap()),
    ]
}

#[cfg(feature = "scalar")]
fn words4(bytes: &[u8; 16]) -> [u32; 4] {
    std::array::from_fn(|i| u32::from_le_bytes(bytes[i * 4..i * 4 + 4].try_into().unwrap()))
}

#[cfg(feature = "scalar")]
fn words8(bytes: &[u8; 32]) -> [u32; 8] {
    std::array::from_fn(|i| u32::from_le_bytes(bytes[i * 4..i * 4 + 4].try_into().unwrap()))
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for &byte in bytes {
        out.push(DIGITS[(byte >> 4) as usize] as char);
        out.push(DIGITS[(byte & 0xf) as usize] as char);
    }
    out
}

fn backend_name() -> &'static str {
    #[cfg(feature = "zlib-rs")]
    { return "zlib-rs"; }
    #[cfg(all(not(feature = "zlib-rs"), feature = "miniz"))]
    { return "miniz"; }
    "unknown"
}

fn salsa_name() -> &'static str {
    #[cfg(feature = "rustcrypto")]
    { return "rustcrypto"; }
    #[cfg(all(not(feature = "rustcrypto"), feature = "scalar"))]
    { return "scalar"; }
    "unknown"
}
