#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include <openssl/sha.h>

/*
 * Source-close T6 PC FastFile/XFile expander.
 *
 * Reproduces the OpenAssetTools T6 loader contract pinned during BO2 reversal:
 * - signed official PC header TAff0100 / version 147;
 * - signed auth header PHEEBs71 + flags + 32-byte filename + 256-byte signature;
 * - four interleaved XChunk streams;
 * - 0x8000 maximum encrypted chunk, 0x80000 vanilla raw-buffer boundary rule;
 * - Treyarch PC Salsa20 key;
 * - per-stream 200x20-byte evolving SHA-1/XOR IV schedule seeded from zone name;
 * - raw DEFLATE after decryption.
 *
 * Authoritative source reference:
 *   Laupetin/OpenAssetTools @ 2ca512abe7cb82d70a94d5ad7846043c3978862d
 *   ZoneLoaderFactoryT6.cpp, ProcessorXChunks.cpp,
 *   AbstractSalsa20Processor.cpp, XChunkProcessorSalsa20Decryption.cpp,
 *   XChunkProcessorInflate.cpp, ZoneConstantsT6.h.
 */

static uint32_t rotl(uint32_t v, int c){return (v<<c)|(v>>(32-c));}
static uint32_t ld32(const uint8_t*p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static void st32(uint8_t*p,uint32_t v){p[0]=v;p[1]=v>>8;p[2]=v>>16;p[3]=v>>24;}
static void salsa20_block(const uint8_t key[32], const uint8_t nonce[8], uint64_t counter, uint8_t out[64]){
    static const uint8_t sigma[16]="expand 32-byte k";
    uint32_t x[16],z[16];
    x[0]=ld32(sigma); x[5]=ld32(sigma+4); x[10]=ld32(sigma+8); x[15]=ld32(sigma+12);
    x[1]=ld32(key);x[2]=ld32(key+4);x[3]=ld32(key+8);x[4]=ld32(key+12);
    x[11]=ld32(key+16);x[12]=ld32(key+20);x[13]=ld32(key+24);x[14]=ld32(key+28);
    x[6]=ld32(nonce);x[7]=ld32(nonce+4);x[8]=(uint32_t)counter;x[9]=(uint32_t)(counter>>32);
    memcpy(z,x,sizeof(x));
    for(int i=0;i<10;i++){
#define QR(a,b,c,d) z[b]^=rotl(z[a]+z[d],7); z[c]^=rotl(z[b]+z[a],9); z[d]^=rotl(z[c]+z[b],13); z[a]^=rotl(z[d]+z[c],18)
        QR(0,4,8,12); QR(5,9,13,1); QR(10,14,2,6); QR(15,3,7,11);
        QR(0,1,2,3); QR(5,6,7,4); QR(10,11,8,9); QR(15,12,13,14);
#undef QR
    }
    for(int i=0;i<16;i++)st32(out+4*i,z[i]+x[i]);
}
static void salsa20_xor(const uint8_t key[32], const uint8_t nonce[8], const uint8_t *in, uint8_t*out, size_t n){
    uint64_t ctr=0; uint8_t ks[64];
    while(n){salsa20_block(key,nonce,ctr++,ks);size_t m=n<64?n:64;for(size_t i=0;i<m;i++)out[i]=in[i]^ks[i];in+=m;out+=m;n-=m;}
}
static const uint8_t key[32]={0x64,0x1D,0x8A,0x2F,0xE3,0x1D,0x3A,0xA6,0x36,0x22,0xBB,0xC9,0xCE,0x85,0x87,0x22,0x9D,0x42,0xB0,0xF8,0xED,0x9B,0x92,0x41,0x30,0xBF,0x88,0xB6,0x5E,0xDC,0x50,0xBE};
int main(int argc,char**argv){
 if(argc<4){fprintf(stderr,"usage: %s in.ff out.bin zoneName\n",argv[0]);return 2;}
 FILE*f=fopen(argv[1],"rb");if(!f){perror("open in");return 1;} FILE*o=fopen(argv[2],"wb");if(!o){perror("open out");return 1;}
 fseek(f,0,SEEK_END); long flen=ftell(f); rewind(f); uint8_t*all=malloc(flen); if(fread(all,1,flen,f)!=(size_t)flen){fprintf(stderr,"read fail\n");return 1;} fclose(f);
 if(flen<312 || memcmp(all,"TAff0100",8)!=0){fprintf(stderr,"bad header\n");return 1;}
 uint32_t ver=ld32(all+8); if(ver!=147){fprintf(stderr,"bad version %u\n",ver);return 1;}
 size_t off=12; if(memcmp(all+off,"PHEEBs71",8)!=0){fprintf(stderr,"bad auth magic\n");return 1;} off+=8+4+32+256;
 const char*zn=argv[3];size_t znlen=strlen(zn);if(!znlen)return 1;if(znlen>31)znlen=31;
 uint8_t hashes[200*4*20]; size_t zoff=0; for(size_t i=0;i<sizeof(hashes);i+=4){memset(hashes+i,(unsigned char)zn[zoff++],4);zoff%=znlen;}
 unsigned idx[4]={0,0,0,0}; size_t rawmod=off%0x80000; unsigned rec=0,counts[4]={0}; size_t totalout=0;
 uint8_t *dec=malloc(0x8000), *decomp=malloc(0x8000); if(!dec||!decomp)return 1;
 while(off+4<=(size_t)flen){
   if(rawmod+4>0x80000){size_t skip=0x80000-rawmod;off+=skip;rawmod=0;if(off+4>(size_t)flen)break;}
   uint32_t cs=ld32(all+off);off+=4;rawmod=(rawmod+4)%0x80000;
   if(cs==0)break;if(cs>0x8000||off+cs>(size_t)flen){fprintf(stderr,"bad chunk %u size=%u off=%zx\n",rec,cs,off);return 1;}
   unsigned s=rec%4;uint8_t*hb=hashes+(idx[s]*4+s)*20;salsa20_xor(key,hb,all+off,dec,cs);
   uint8_t sha[20];SHA1(dec,cs,sha);idx[s]=(idx[s]+1)%200;uint8_t*next=hashes+(idx[s]*4+s)*20;for(int j=0;j<20;j++)next[j]^=sha[j];
   z_stream zs;memset(&zs,0,sizeof(zs));if(inflateInit2(&zs,-MAX_WBITS)!=Z_OK){fprintf(stderr,"inflate init\n");return 1;}zs.next_in=dec;zs.avail_in=cs;zs.next_out=decomp;zs.avail_out=0x8000;int zr=inflate(&zs,Z_FULL_FLUSH);if(zr!=Z_STREAM_END){fprintf(stderr,"inflate fail rec=%u stream=%u cs=%u zr=%d msg=%s\n",rec,s,cs,zr,zs.msg?zs.msg:"");return 1;}size_t outn=zs.total_out;inflateEnd(&zs);fwrite(decomp,1,outn,o);totalout+=outn;counts[s]++;
   off+=cs;rawmod=(rawmod+cs)%0x80000;rec++;
 }
 fclose(o);fprintf(stderr,"records=%u counts=%u/%u/%u/%u out=%zu raw_off=%zx\n",rec,counts[0],counts[1],counts[2],counts[3],totalout,off);free(dec);free(decomp);free(all);return 0;
}
