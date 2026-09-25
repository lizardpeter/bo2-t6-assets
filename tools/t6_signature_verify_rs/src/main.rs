use std::{env, fs, path::PathBuf};

use rsa::{pkcs1::DecodeRsaPublicKey, traits::PublicKeyParts, BigUint, RsaPublicKey};
use sha2::{Digest, Sha256};

const SIGNATURE_OFFSET: usize = 56;
const SIGNATURE_BYTES: usize = 256;
const HASH_TABLE_BYTES: usize = 200 * 4 * 20;
const PSS_SALT_BYTES: usize = 8;

const TREYARCH_RSA_PUBLIC_KEY_DER: [u8; 270] = [
    0x30, 0x82, 0x01, 0x0a, 0x02, 0x82, 0x01, 0x01, 0x00, 0xc7, 0x9d, 0x33,
    0xe0, 0x75, 0xaf, 0xef, 0x08, 0x08, 0x2b, 0x89, 0xd9, 0x3b, 0xf3, 0xd5,
    0x9a, 0x65, 0xa6, 0xde, 0x3b, 0x1e, 0x20, 0xde, 0x59, 0x19, 0x43, 0x88,
    0x1a, 0x8b, 0x39, 0x13, 0x60, 0x12, 0xd3, 0xb2, 0x77, 0x6d, 0xe1, 0x99,
    0x75, 0x24, 0xb4, 0x0d, 0x8c, 0xb7, 0x84, 0xf2, 0x48, 0x8f, 0xd5, 0x4c,
    0xb7, 0x64, 0x44, 0xa3, 0xa8, 0x4a, 0xac, 0x2d, 0x54, 0x15, 0x2b, 0x1f,
    0xb3, 0xf4, 0x4c, 0x16, 0xa0, 0x92, 0x8e, 0xd2, 0xfa, 0xcc, 0x11, 0x6a,
    0x74, 0x6a, 0x70, 0xb8, 0xd3, 0x34, 0x6b, 0x39, 0xc6, 0x2a, 0x69, 0xde,
    0x31, 0x34, 0xdf, 0xe7, 0x8b, 0x7e, 0x17, 0xa3, 0x17, 0xd9, 0x5e, 0x88,
    0x39, 0x21, 0xf8, 0x7d, 0x3c, 0x29, 0x21, 0x6c, 0x0e, 0xf1, 0xb4, 0x09,
    0x54, 0xe8, 0x20, 0x34, 0x90, 0x2e, 0xb4, 0x1a, 0x95, 0x95, 0x90, 0xe5,
    0xfb, 0xce, 0xfe, 0x8a, 0xbf, 0xea, 0xaf, 0x09, 0x0c, 0x0b, 0x87, 0x22,
    0xe1, 0xfe, 0x82, 0x6e, 0x91, 0xe8, 0xd1, 0xb6, 0x35, 0x03, 0x4f, 0xdb,
    0xc1, 0x31, 0xe2, 0xba, 0xa0, 0x13, 0xf6, 0xdb, 0x07, 0x9b, 0xcb, 0x99,
    0xce, 0x9f, 0x49, 0xc4, 0x51, 0x8e, 0xf1, 0x04, 0x9b, 0x30, 0xc3, 0x02,
    0xff, 0x7b, 0x94, 0xca, 0x12, 0x69, 0x1e, 0xdb, 0x2d, 0x3e, 0xbd, 0x48,
    0x16, 0xe1, 0x72, 0x37, 0xb8, 0x5f, 0x61, 0xfa, 0x24, 0x16, 0x3a, 0xde,
    0xbf, 0x6a, 0x71, 0x62, 0x32, 0xf3, 0xaa, 0x7f, 0x28, 0x3a, 0x0c, 0x27,
    0xeb, 0xa9, 0x0a, 0x4c, 0x79, 0x88, 0x84, 0xb3, 0xe2, 0x52, 0xb9, 0x68,
    0x1e, 0x82, 0xcf, 0x67, 0x43, 0xf3, 0x68, 0xf7, 0x26, 0x19, 0xaa, 0xdd,
    0x3f, 0x1e, 0xc6, 0x46, 0x11, 0x9f, 0x24, 0x23, 0xa7, 0xb0, 0x1b, 0x79,
    0xa7, 0x0c, 0x5a, 0xfe, 0x96, 0xf7, 0xe7, 0x88, 0x09, 0xa6, 0x69, 0xe3,
    0x8b, 0x02, 0x03, 0x01, 0x00, 0x01,
];

fn main() {
    if let Err(error) = run() {
        eprintln!("t6-fastfile-signature-verify: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let ff = PathBuf::from(args.next().ok_or_else(|| "usage: t6-fastfile-signature-verify <retail.ff> <final_hash_table.bin>".to_owned())?);
    let table = PathBuf::from(args.next().ok_or_else(|| "missing final hash table".to_owned())?);
    if args.next().is_some() {
        return Err("too many arguments".to_owned());
    }

    let ff = fs::read(&ff).map_err(|error| format!("failed to read FastFile: {error}"))?;
    let table = fs::read(&table).map_err(|error| format!("failed to read final hash table: {error}"))?;
    let signature = ff
        .get(SIGNATURE_OFFSET..SIGNATURE_OFFSET + SIGNATURE_BYTES)
        .ok_or_else(|| "FastFile signature field is truncated".to_owned())?;
    if table.len() != HASH_TABLE_BYTES {
        return Err(format!("final hash table is {} bytes; expected {HASH_TABLE_BYTES}", table.len()));
    }

    let key = RsaPublicKey::from_pkcs1_der(&TREYARCH_RSA_PUBLIC_KEY_DER)
        .map_err(|error| format!("failed to parse Treyarch RSA key: {error}"))?;
    verify_libtomcrypt_pss(&key, signature, &table)?;

    println!("T6_RSA_SIGNATURE_VALID hash_table_bytes={} signature_bytes={} salt_bytes={}", table.len(), signature.len(), PSS_SALT_BYTES);
    Ok(())
}


fn verify_libtomcrypt_pss(
    key: &RsaPublicKey,
    signature: &[u8],
    message_hash_bytes: &[u8],
) -> Result<(), String> {
    let modulus_bits = key.n().bits() as usize;
    let modulus_bytes = key.size();
    if signature.len() != modulus_bytes {
        return Err(format!(
            "RSA signature is {} bytes; modulus requires {modulus_bytes}",
            signature.len()
        ));
    }

    let sig_int = BigUint::from_bytes_be(signature);
    if &sig_int >= key.n() {
        return Err("RSA signature representative is outside modulus".to_owned());
    }
    let em_int = sig_int.modpow(key.e(), key.n());
    let raw = em_int.to_bytes_be();
    if raw.len() > modulus_bytes {
        return Err("raw RSA result exceeds modulus width".to_owned());
    }
    let mut em_full = vec![0u8; modulus_bytes];
    em_full[modulus_bytes - raw.len()..].copy_from_slice(&raw);

    let em_bits = modulus_bits
        .checked_sub(1)
        .ok_or_else(|| "invalid zero-bit RSA modulus".to_owned())?;
    let em_len = (em_bits + 7) / 8;
    let em = &em_full[modulus_bytes - em_len..];

    const H_LEN: usize = 32;
    if em_len < H_LEN + PSS_SALT_BYTES + 2 {
        return Err("RSA modulus is too short for T6 PSS".to_owned());
    }
    if em.last().copied() != Some(0xbc) {
        return Err("T6 PSS trailer byte is not 0xBC".to_owned());
    }

    let db_len = em_len - H_LEN - 1;
    let (masked_db, tail) = em.split_at(db_len);
    let h = &tail[..H_LEN];

    let unused_bits = em_len * 8 - em_bits;
    let forbidden_mask = 0xffu8
        .checked_shl((8 - unused_bits) as u32)
        .unwrap_or(0);
    if masked_db[0] & forbidden_mask != 0 {
        return Err("T6 PSS encoded message has forbidden high bits".to_owned());
    }

    let mut db = masked_db.to_vec();
    mgf1_xor_sha256(&mut db, h);
    db[0] &= 0xff >> unused_bits;

    let ps_len = em_len - PSS_SALT_BYTES - H_LEN - 2;
    if db[..ps_len].iter().any(|byte| *byte != 0) {
        return Err("T6 PSS zero padding is invalid".to_owned());
    }
    if db[ps_len] != 0x01 {
        return Err("T6 PSS separator is not 0x01".to_owned());
    }
    let salt = &db[db.len() - PSS_SALT_BYTES..];

    let mut sha = Sha256::new();
    sha.update([0u8; 8]);
    sha.update(message_hash_bytes);
    sha.update(salt);
    let expected_h = sha.finalize();

    if expected_h.as_slice() != h {
        return Err("T6 LibTomCrypt-compatible PSS digest mismatch".to_owned());
    }
    Ok(())
}

fn mgf1_xor_sha256(target: &mut [u8], seed: &[u8]) {
    let mut counter = 0u32;
    let mut offset = 0usize;
    while offset < target.len() {
        let mut sha = Sha256::new();
        sha.update(seed);
        sha.update(counter.to_be_bytes());
        let block = sha.finalize();
        let count = (target.len() - offset).min(block.len());
        for index in 0..count {
            target[offset + index] ^= block[index];
        }
        offset += count;
        counter = counter.wrapping_add(1);
    }
}
