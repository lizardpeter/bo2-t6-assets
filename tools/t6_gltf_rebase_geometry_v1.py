#!/usr/bin/env python3
import argparse, json, struct, hashlib
from pathlib import Path

MAGIC=b'glTF'; JSON_CHUNK=0x4E4F534A; BIN_CHUNK=0x004E4942
COMP={5120:('b',1),5121:('B',1),5122:('h',2),5123:('H',2),5125:('I',4),5126:('f',4)}
NCOMP={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
ATTRS=('POSITION','NORMAL','TEXCOORD_0','JOINTS_0','WEIGHTS_0')

def load_glb(path):
    data=Path(path).read_bytes()
    magic,ver,total=struct.unpack_from('<4sII',data,0)
    if magic!=MAGIC or ver!=2 or total!=len(data): raise SystemExit(f'invalid GLB: {path}')
    off=12; js=None; binb=None
    while off<total:
        n,t=struct.unpack_from('<II',data,off); off+=8; chunk=data[off:off+n]; off+=n
        if t==JSON_CHUNK: js=json.loads(chunk.decode('utf-8').rstrip(' \x00'))
        elif t==BIN_CHUNK: binb=bytearray(chunk)
    if js is None or binb is None: raise SystemExit(f'missing GLB chunks: {path}')
    return js,binb

def acc_values(js,binb,idx):
    a=js['accessors'][idx]
    if 'sparse' in a: raise SystemExit('sparse accessors unsupported')
    bv=js['bufferViews'][a['bufferView']]
    fmt,sz=COMP[a['componentType']]; nc=NCOMP[a['type']]
    base=bv.get('byteOffset',0)+a.get('byteOffset',0); stride=bv.get('byteStride',sz*nc)
    out=[]
    for i in range(a['count']):
        out.append(struct.unpack_from('<'+fmt*nc,binb,base+i*stride))
    return out

def write_acc(js,binb,idx,vals):
    a=js['accessors'][idx]; bv=js['bufferViews'][a['bufferView']]
    fmt,sz=COMP[a['componentType']]; nc=NCOMP[a['type']]
    if len(vals)!=a['count']: raise SystemExit('accessor count mismatch')
    base=bv.get('byteOffset',0)+a.get('byteOffset',0); stride=bv.get('byteStride',sz*nc)
    for i,row in enumerate(vals):
        raw=struct.pack('<'+fmt*nc,*row)
        pos=base+i*stride; binb[pos:pos+len(raw)]=raw

def save_glb(path,js,binb):
    j=json.dumps(js,separators=(',',':'),ensure_ascii=False).encode(); j+=b' '*((-len(j))%4)
    b=bytes(binb); b+=b'\x00'*((-len(b))%4)
    total=12+8+len(j)+8+len(b)
    Path(path).write_bytes(struct.pack('<4sII',MAGIC,2,total)+struct.pack('<II',len(j),JSON_CHUNK)+j+struct.pack('<II',len(b),BIN_CHUNK)+b)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--carrier',required=True); ap.add_argument('--authority',required=True); ap.add_argument('--output',required=True); ap.add_argument('--report',required=True)
    ap.add_argument('--require-primitives',type=int); ap.add_argument('--require-materials',type=int); ap.add_argument('--require-images',type=int); ap.add_argument('--require-animations',type=int)
    args=ap.parse_args()
    cjs,cbin=load_glb(args.carrier); ajs,abin=load_glb(args.authority)
    cp=cjs['meshes'][0]['primitives']; apm=ajs['meshes'][0]['primitives']
    if len(cp)!=len(apm): raise SystemExit('primitive count mismatch')
    if args.require_primitives is not None and len(cp)!=args.require_primitives: raise SystemExit('unexpected primitive count')
    gates=[]
    for i,(c,a) in enumerate(zip(cp,apm)):
        if 'COLOR_0' not in c['attributes']: raise SystemExit(f'carrier primitive {i} missing expected stale COLOR_0')
        if 'COLOR_0' in a['attributes']: raise SystemExit(f'authority primitive {i} unexpectedly has COLOR_0')
        for k in ATTRS:
            if acc_values(cjs,cbin,c['attributes'][k])!=acc_values(ajs,abin,a['attributes'][k]): raise SystemExit(f'primitive {i} {k} differs')
        ci=acc_values(cjs,cbin,c['indices']); ai=acc_values(ajs,abin,a['indices'])
        if len(ci)%3: raise SystemExit(f'primitive {i} non-triangle index count')
        flipped=[]
        for t in range(0,len(ci),3): flipped.extend((ci[t],ci[t+2],ci[t+1]))
        if flipped!=ai: raise SystemExit(f'primitive {i} authority indices are not exact winding reversal')
        write_acc(cjs,cbin,c['indices'],ai)
        del c['attributes']['COLOR_0']
        gates.append({'primitive':i,'vertexAttributesExact':True,'authorityWindingExact':True,'color0Removed':True,'triangles':len(ai)//3})
    if any('COLOR_0' in p['attributes'] for p in cp): raise SystemExit('COLOR_0 survived rebase')
    for key,req in [('materials',args.require_materials),('images',args.require_images),('animations',args.require_animations)]:
        if req is not None and len(cjs.get(key,[]))!=req: raise SystemExit(f'unexpected {key} count')
    cjs.setdefault('asset',{})['generator']=(cjs.get('asset',{}).get('generator','')+' | T6 authoritative geometry v3 rebase').strip()
    save_glb(args.output,cjs,cbin)
    ojs,obin=load_glb(args.output)
    if any('COLOR_0' in p['attributes'] for p in ojs['meshes'][0]['primitives']): raise SystemExit('output COLOR_0 validation failed')
    for i,(o,a) in enumerate(zip(ojs['meshes'][0]['primitives'],apm)):
        if acc_values(ojs,obin,o['indices'])!=acc_values(ajs,abin,a['indices']): raise SystemExit(f'output primitive {i} indices differ from authority')
    report={'format':'t6-gltf-geometry-rebase-v1','carrier':str(args.carrier),'authority':str(args.authority),'output':str(args.output),'primitiveCount':len(cp),'materials':len(ojs.get('materials',[])),'images':len(ojs.get('images',[])),'animations':len(ojs.get('animations',[])),'color0Present':False,'gates':gates,'outputSha256':hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),'authoritative':True}
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__': main()
