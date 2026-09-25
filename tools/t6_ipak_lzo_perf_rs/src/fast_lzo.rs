// T6 benchmark variant of SecurityRonin/lzo's Apache-2.0 safe LZO1X
// decompressor. The instruction decoder and validation model remain the same;
// copy_match is specialized to use bulk non-overlap copies and geometric
// overlap expansion instead of one byte per output byte.

#[derive(Debug, Clone, Copy)]
pub enum Error {
    InputOverrun,
    OutputOverrun,
    LookbehindOverrun,
    InputNotConsumed,
    Malformed,
}

#[inline]
fn rd(src: &[u8], ip: &mut usize) -> Result<u8, Error> {
    let b = *src.get(*ip).ok_or(Error::InputOverrun)?;
    *ip += 1;
    Ok(b)
}

#[inline]
fn rd_le16(src: &[u8], ip: &mut usize) -> Result<usize, Error> {
    let lo = rd(src, ip)? as usize;
    let hi = rd(src, ip)? as usize;
    Ok(lo | (hi << 8))
}

#[inline]
fn length_ext(src: &[u8], ip: &mut usize) -> Result<usize, Error> {
    let mut zeros = 0usize;
    while *src.get(*ip).ok_or(Error::InputOverrun)? == 0 {
        *ip += 1;
        zeros += 1;
    }
    let term = rd(src, ip)? as usize;
    Ok(zeros.saturating_mul(255).saturating_add(term))
}

#[inline]
fn copy_literals(
    src: &[u8],
    ip: &mut usize,
    dst: &mut [u8],
    op: &mut usize,
    n: usize,
) -> Result<(), Error> {
    if n > dst.len().saturating_sub(*op) {
        return Err(Error::OutputOverrun);
    }
    if n > src.len().saturating_sub(*ip) {
        return Err(Error::InputOverrun);
    }
    dst[*op..*op + n].copy_from_slice(&src[*ip..*ip + n]);
    *op += n;
    *ip += n;
    Ok(())
}

#[inline]
fn copy_match(
    dst: &mut [u8],
    op: &mut usize,
    distance: usize,
    length: usize,
) -> Result<(), Error> {
    if distance == 0 || distance > *op {
        return Err(Error::LookbehindOverrun);
    }
    if length > dst.len().saturating_sub(*op) {
        return Err(Error::OutputOverrun);
    }

    let dest = *op;
    let source = dest - distance;

    if distance >= length {
        let (before, after) = dst.split_at_mut(dest);
        after[..length].copy_from_slice(&before[source..source + length]);
    } else {
        // Seed one complete match-distance period with a non-overlapping copy.
        let (before, after) = dst.split_at_mut(dest);
        after[..distance].copy_from_slice(&before[source..source + distance]);

        // The destination now contains valid source data. Doubling the
        // initialized prefix preserves LZ77 overlap semantics while turning
        // long repeated matches into O(log n) bulk copies.
        let region = &mut after[..length];
        let mut initialized = distance;
        while initialized < length {
            let copy = initialized.min(length - initialized);
            let (ready, pending) = region.split_at_mut(initialized);
            pending[..copy].copy_from_slice(&ready[..copy]);
            initialized += copy;
        }
    }

    *op += length;
    Ok(())
}

pub fn decompress_into(src: &[u8], dst: &mut [u8]) -> Result<usize, Error> {
    if src.len() < 3 {
        return Err(Error::InputOverrun);
    }

    let mut ip = 0usize;
    let mut op = 0usize;
    let mut state: usize;
    let mut t: usize;

    let first = src[0];
    if first > 17 {
        ip = 1;
        t = first as usize - 17;
        copy_literals(src, &mut ip, dst, &mut op, t)?;
        state = if t < 4 { t } else { 4 };
    } else {
        state = 0;
    }

    loop {
        t = rd(src, &mut ip)? as usize;
        let (distance, length, next);

        if t < 16 {
            if state == 0 {
                let len = if t == 0 {
                    length_ext(src, &mut ip)?.saturating_add(18)
                } else {
                    t + 3
                };
                copy_literals(src, &mut ip, dst, &mut op, len)?;
                state = 4;
                continue;
            }

            next = t & 3;
            if state == 4 {
                distance = 1 + 2048 + (t >> 2) + ((rd(src, &mut ip)? as usize) << 2);
                length = 3;
            } else {
                distance = 1 + (t >> 2) + ((rd(src, &mut ip)? as usize) << 2);
                length = 2;
            }
        } else if t >= 64 {
            next = t & 3;
            distance = 1 + ((t >> 2) & 7) + ((rd(src, &mut ip)? as usize) << 3);
            length = (t >> 5) + 1;
        } else if t >= 32 {
            length = if (t & 31) == 0 {
                length_ext(src, &mut ip)?.saturating_add(33)
            } else {
                (t & 31) + 2
            };
            let d = rd_le16(src, &mut ip)?;
            distance = 1 + (d >> 2);
            next = d & 3;
        } else {
            let hi = (t & 8) << 11;
            length = if (t & 7) == 0 {
                length_ext(src, &mut ip)?.saturating_add(9)
            } else {
                (t & 7) + 2
            };
            let d = rd_le16(src, &mut ip)?;
            let dist_part = d >> 2;
            next = d & 3;

            if hi == 0 && dist_part == 0 {
                if length != 3 {
                    return Err(Error::Malformed);
                }
                if ip < src.len() {
                    return Err(Error::InputNotConsumed);
                }
                return Ok(op);
            }
            distance = hi + dist_part + 0x4000;
        }

        copy_match(dst, &mut op, distance, length)?;
        copy_literals(src, &mut ip, dst, &mut op, next)?;
        state = next;
    }
}
