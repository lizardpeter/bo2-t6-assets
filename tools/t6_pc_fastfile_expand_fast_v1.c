/*
 * Fast T6 PC signed fastfile expander v1.
 *
 * This is an optional accelerator for tools/t6_pc_fastfile_expand_v1.py. It
 * preserves the exact retail loader semantics: four interleaved XChunk streams,
 * Treyarch T6 PC Salsa20, the evolving per-stream SHA1 hash-block IV scheme,
 * and raw-DEFLATE after decryption.
 *
 * Validation fixture, 2026-09-05:
 *   faction_seals_mp.ff -> 6,245,916 expanded bytes
 *   SHA-256 21a11090990417faefa8c39282f499c7bdb87a7acf62f00082aa9b3811cced30
 *   byte-identical to the canonical Python expander.
 *   common_mp.ff -> 206,493,911 expanded bytes
 *   SHA-256 fbd91d0ede8e27bcaaf7af9638a7118050f27519524be36e9234f980bd6170ce
 *
 * Build example: cc -O3 t6_pc_fastfile_expand_fast_v1.c -o t6_expand -lz -lcrypto
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include <openssl/sha.h>

#define STREAMS 4
#define BLOCKS 200
#define SHA1SZ 20
#define XCHUNK 0x8000

static const uint8_t KEY[32] = {
    0x64,0x1D,0x8A,0x2F,0xE3,0x1D,0x3A,0xA6,0x36,0x22,0xBB,0xC9,0xCE,0x85,0x87,0x22,
    0x9D,0x42,0xB0,0xF8,0xED,0x9B,0x92,0x41,0x30,0xBF,0x88,0xB6,0x5E,0xDC,0x50,0xBE
};

static uint32_t rd32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void wr32(uint8_t *p, uint32_t v) { p[0]=v; p[1]=v>>8; p[2]=v>>16; p[3]=v>>24; }
static uint32_t rotl(uint32_t x, int n) { return (x << n) | (x >> (32 - n)); }

static void salsa_block(const uint8_t key[32], const uint8_t nonce[8], uint64_t ctr, uint8_t out[64]) {
    static const uint8_t sigma[16] = "expand 32-byte k";
    uint32_t x[16], z[16];
    x[0]=rd32(sigma); x[1]=rd32(key); x[2]=rd32(key+4); x[3]=rd32(key+8); x[4]=rd32(key+12);
    x[5]=rd32(sigma+4); x[6]=rd32(nonce); x[7]=rd32(nonce+4); x[8]=(uint32_t)ctr; x[9]=(uint32_t)(ctr>>32);
    x[10]=rd32(sigma+8); x[11]=rd32(key+16); x[12]=rd32(key+20); x[13]=rd32(key+24); x[14]=rd32(key+28); x[15]=rd32(sigma+12);
    memcpy(z, x, sizeof z);
    for (int r=0; r<10; r++) {
        z[4]^=rotl(z[0]+z[12],7); z[8]^=rotl(z[4]+z[0],9); z[12]^=rotl(z[8]+z[4],13); z[0]^=rotl(z[12]+z[8],18);
        z[9]^=rotl(z[5]+z[1],7); z[13]^=rotl(z[9]+z[5],9); z[1]^=rotl(z[13]+z[9],13); z[5]^=rotl(z[1]+z[13],18);
        z[14]^=rotl(z[10]+z[6],7); z[2]^=rotl(z[14]+z[10],9); z[6]^=rotl(z[2]+z[14],13); z[10]^=rotl(z[6]+z[2],18);
        z[3]^=rotl(z[15]+z[11],7); z[7]^=rotl(z[3]+z[15],9); z[11]^=rotl(z[7]+z[3],13); z[15]^=rotl(z[11]+z[7],18);
        z[1]^=rotl(z[0]+z[3],7); z[2]^=rotl(z[1]+z[0],9); z[3]^=rotl(z[2]+z[1],13); z[0]^=rotl(z[3]+z[2],18);
        z[6]^=rotl(z[5]+z[4],7); z[7]^=rotl(z[6]+z[5],9); z[4]^=rotl(z[7]+z[6],13); z[5]^=rotl(z[4]+z[7],18);
        z[11]^=rotl(z[10]+z[9],7); z[8]^=rotl(z[11]+z[10],9); z[9]^=rotl(z[8]+z[11],13); z[10]^=rotl(z[9]+z[8],18);
        z[12]^=rotl(z[15]+z[14],7); z[13]^=rotl(z[12]+z[15],9); z[14]^=rotl(z[13]+z[12],13); z[15]^=rotl(z[14]+z[13],18);
    }
    for (int i=0; i<16; i++) wr32(out + 4*i, z[i] + x[i]);
}

static void salsa_xor(uint8_t *d, size_t n, const uint8_t nonce[8]) {
    uint64_t ctr=0; size_t p=0; uint8_t ks[64];
    while (p<n) {
        salsa_block(KEY, nonce, ctr++, ks);
        size_t m = n-p < 64 ? n-p : 64;
        for (size_t i=0; i<m; i++) d[p+i] ^= ks[i];
        p += m;
    }
}

static int inflate_raw(const uint8_t *in, size_t inlen, uint8_t *out, size_t *outlen) {
    z_stream z={0};
    if (inflateInit2(&z, -MAX_WBITS) != Z_OK) return -1;
    z.next_in=(Bytef*)in; z.avail_in=(uInt)inlen; z.next_out=out; z.avail_out=XCHUNK;
    int r=inflate(&z, Z_FINISH);
    if (r != Z_STREAM_END) { inflateEnd(&z); return r; }
    *outlen=z.total_out; inflateEnd(&z); return Z_OK;
}

int main(int argc, char **argv) {
    if (argc < 3) { fprintf(stderr, "usage: %s in.ff out.bin\n", argv[0]); return 2; }
    FILE *f=fopen(argv[1], "rb"); if (!f) { perror("open input"); return 2; }
    fseek(f,0,SEEK_END); long fl=ftell(f); fseek(f,0,SEEK_SET);
    uint8_t *d=malloc(fl);
    if (!d || fread(d,1,fl,f)!=(size_t)fl) { fprintf(stderr,"read fail\n"); return 2; }
    fclose(f);
    if (fl<312 || memcmp(d,"TAff0100",8) || rd32(d+8)!=147 || memcmp(d+12,"PHEEBs71",8)) {
        fprintf(stderr,"bad header\n"); return 2;
    }
    char zone[33]={0}; memcpy(zone,d+24,32); size_t zn=strnlen(zone,32);
    if (!zn) { fprintf(stderr,"empty zone\n"); return 2; }

    uint8_t hashes[BLOCKS*STREAMS*SHA1SZ];
    size_t j=0;
    for (size_t i=0; i<sizeof hashes; i+=4) { memset(hashes+i,(uint8_t)zone[j],4); j=(j+1)%zn; }
    unsigned idx[STREAMS]={0};
    size_t off=12+8+4+32+256;
    FILE *out=fopen(argv[2],"wb"); if (!out) { perror("open output"); return 2; }
    uint8_t comp[XCHUNK], plain[XCHUNK]; size_t chunks=0, expanded=0;
    while (off+4 <= (size_t)fl) {
        size_t sizeoff=off; uint32_t sz=rd32(d+off); off+=4;
        if (sz==0) break;
        if (sz>XCHUNK || off+sz>(size_t)fl) { fprintf(stderr,"bad chunk %zu sz %u at %zx\n",chunks,sz,sizeoff); return 3; }
        memcpy(comp,d+off,sz); off+=sz;
        unsigned s=chunks%STREAMS;
        size_t bo=(size_t)idx[s]*STREAMS*SHA1SZ+(size_t)s*SHA1SZ;
        uint8_t iv[8]; memcpy(iv,hashes+bo,8); salsa_xor(comp,sz,iv);
        size_t plen=0; int zr=inflate_raw(comp,sz,plain,&plen);
        if (zr!=Z_OK) { fprintf(stderr,"inflate fail chunk %zu stream %u code %d\n",chunks,s,zr); return 4; }
        if (fwrite(plain,1,plen,out)!=plen) { fprintf(stderr,"write fail\n"); return 5; }
        uint8_t h[20]; SHA1(comp,sz,h);
        idx[s]=(idx[s]+1)%BLOCKS;
        bo=(size_t)idx[s]*STREAMS*SHA1SZ+(size_t)s*SHA1SZ;
        for (int k=0;k<20;k++) hashes[bo+k]^=h[k];
        expanded+=plen; chunks++;
    }
    fclose(out);
    fprintf(stderr,"zone=%s chunks=%zu expanded=%zu terminal=%zu remaining=%ld\n",zone,chunks,expanded,off,fl-(long)off);
    free(d);
    return 0;
}
