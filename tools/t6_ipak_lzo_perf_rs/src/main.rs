mod fast_lzo;

use std::{
    env,
    fs,
    hint::black_box,
    path::{Path, PathBuf},
    time::Instant,
};

struct Block {
    compressed: Vec<u8>,
    expected: Vec<u8>,
    out: Vec<u8>,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("t6-ipak-lzo-perf: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let dir = PathBuf::from(
        args.next()
            .ok_or_else(|| "usage: t6-ipak-lzo-perf <corpus-dir> [rounds]".to_owned())?,
    );
    let rounds = args
        .next()
        .map(|s| s.parse::<usize>().map_err(|e| format!("bad rounds: {e}")))
        .transpose()?
        .unwrap_or(2000)
        .max(1);
    if args.next().is_some() {
        return Err("too many arguments".to_owned());
    }

    let source = load_blocks(&dir)?;
    if source.is_empty() {
        return Err("corpus contains no LZO commands".to_owned());
    }
    verify_all(&source)?;

    let total_decoded: usize = source.iter().map(|b| b.expected.len()).sum();
    println!(
        "T6_LZO_CORPUS blocks={} decoded_bytes_per_round={}",
        source.len(),
        total_decoded
    );

    bench_lzo(&source, rounds, total_decoded)?;
    bench_fast_lzo(&source, rounds, total_decoded)?;
    bench_lzokay(&source, rounds, total_decoded)?;
    bench_lzo1x(&source, rounds, total_decoded)?;
    Ok(())
}

fn load_blocks(dir: &Path) -> Result<Vec<Block>, String> {
    let mut compressed = fs::read_dir(dir)
        .map_err(|e| format!("failed to read {}: {e}", dir.display()))?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("lzo"))
        .collect::<Vec<_>>();
    compressed.sort();

    let mut out = Vec::with_capacity(compressed.len());
    for path in compressed {
        let raw_path = path.with_extension("raw");
        let c = fs::read(&path).map_err(|e| format!("read {}: {e}", path.display()))?;
        let expected =
            fs::read(&raw_path).map_err(|e| format!("read {}: {e}", raw_path.display()))?;
        out.push(Block {
            compressed: c,
            out: vec![0u8; expected.len()],
            expected,
        });
    }
    Ok(out)
}

fn verify_all(source: &[Block]) -> Result<(), String> {
    for (index, block) in source.iter().enumerate() {
        let mut out = vec![0u8; block.expected.len()];
        let n = lzo::decompress_into(&block.compressed, &mut out)
            .map_err(|e| format!("lzo block {index}: {e:?}"))?;
        if n != block.expected.len() || out != block.expected {
            return Err(format!("lzo block {index} identity mismatch"));
        }

        out.fill(0);
        let n = lzokay::decompress::decompress(&block.compressed, &mut out)
            .map_err(|e| format!("lzokay block {index}: {e:?}"))?;
        if n != block.expected.len() || out != block.expected {
            return Err(format!("lzokay block {index} identity mismatch"));
        }

        out.fill(0);
        let n = fast_lzo::decompress_into(&block.compressed, &mut out)
            .map_err(|e| format!("fast-lzo block {index}: {e:?}"))?;
        if n != block.expected.len() || out[..n] != block.expected {
            return Err(format!("fast-lzo block {index} identity mismatch"));
        }

        out.fill(0);
        lzo1x::decompress(&block.compressed, &mut out)
            .map_err(|e| format!("lzo1x block {index}: {e:?}"))?;
        if out != block.expected {
            return Err(format!("lzo1x block {index} identity mismatch"));
        }
    }
    Ok(())
}

fn fresh(source: &[Block]) -> Vec<Block> {
    source
        .iter()
        .map(|b| Block {
            compressed: b.compressed.clone(),
            expected: b.expected.clone(),
            out: vec![0u8; b.expected.len()],
        })
        .collect()
}

fn report(name: &str, seconds: f64, rounds: usize, decoded_per_round: usize) {
    let decoded_mib = decoded_per_round as f64 * rounds as f64 / 1048576.0;
    println!(
        "T6_LZO_PERF decoder={} rounds={} seconds={:.6} decoded_mib_s={:.3}",
        name,
        rounds,
        seconds,
        decoded_mib / seconds
    );
}

fn bench_lzo(source: &[Block], rounds: usize, decoded_per_round: usize) -> Result<(), String> {
    let mut blocks = fresh(source);
    let start = Instant::now();
    for _ in 0..rounds {
        for block in &mut blocks {
            let n = lzo::decompress_into(black_box(&block.compressed), black_box(&mut block.out))
                .map_err(|e| format!("lzo benchmark: {e:?}"))?;
            if n != block.expected.len() {
                return Err("lzo benchmark output length drift".to_owned());
            }
            black_box(&block.out[..n]);
        }
    }
    report("lzo-0.1.3", start.elapsed().as_secs_f64(), rounds, decoded_per_round);
    Ok(())
}

fn bench_fast_lzo(source: &[Block], rounds: usize, decoded_per_round: usize) -> Result<(), String> {
    let mut blocks = fresh(source);
    let start = Instant::now();
    for _ in 0..rounds {
        for block in &mut blocks {
            let n = fast_lzo::decompress_into(
                black_box(&block.compressed),
                black_box(&mut block.out),
            )
            .map_err(|e| format!("fast-lzo benchmark: {e:?}"))?;
            if n != block.expected.len() {
                return Err("fast-lzo benchmark output length drift".to_owned());
            }
            black_box(&block.out[..n]);
        }
    }
    report(
        "t6-apache-bulk-copy",
        start.elapsed().as_secs_f64(),
        rounds,
        decoded_per_round,
    );
    Ok(())
}

fn bench_lzokay(source: &[Block], rounds: usize, decoded_per_round: usize) -> Result<(), String> {
    let mut blocks = fresh(source);
    let start = Instant::now();
    for _ in 0..rounds {
        for block in &mut blocks {
            let n = lzokay::decompress::decompress(
                black_box(&block.compressed),
                black_box(&mut block.out),
            )
            .map_err(|e| format!("lzokay benchmark: {e:?}"))?;
            if n != block.expected.len() {
                return Err("lzokay benchmark output length drift".to_owned());
            }
            black_box(&block.out[..n]);
        }
    }
    report("lzokay-2.0.1", start.elapsed().as_secs_f64(), rounds, decoded_per_round);
    Ok(())
}

fn bench_lzo1x(source: &[Block], rounds: usize, decoded_per_round: usize) -> Result<(), String> {
    let mut blocks = fresh(source);
    let start = Instant::now();
    for _ in 0..rounds {
        for block in &mut blocks {
            lzo1x::decompress(
                black_box(&block.compressed),
                black_box(&mut block.out),
            )
            .map_err(|e| format!("lzo1x benchmark: {e:?}"))?;
            black_box(&block.out);
        }
    }
    report("lzo1x-0.2.2", start.elapsed().as_secs_f64(), rounds, decoded_per_round);
    Ok(())
}
