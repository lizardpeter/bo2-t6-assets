#!/usr/bin/env python3
"""Prove ordinary T6 animated root translation composition from retail t6mp.exe.

Pinned to one exact retail PC executable. This verifier independently binds the
primary DObj skeleton path:
- root bones are finalized by the root helpers without XModel.trans[];
- non-root bones are routed to the compact model transform helper at
  boneIndex + numRootBones;
- that non-root helper reads XModel.parentList and XModel.trans and adds the
  compact bind-local translation before parent-space composition.

This is separate from XAnimParts.deltaPart root motion.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

EXPECTED_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
IMAGE_BASE = 0x400000

class ProofError(RuntimeError): pass

class PE:
    def __init__(self, path: Path):
        self.path=path; self.data=path.read_bytes()
        if self.data[:2] != b"MZ": raise ProofError("not MZ")
        pe=struct.unpack_from("<I",self.data,0x3C)[0]
        if self.data[pe:pe+4] != b"PE\0\0": raise ProofError("not PE")
        coff=pe+4
        machine,nsects,_,_,_,opt_size,_=struct.unpack_from("<HHIIIHH",self.data,coff)
        if machine != 0x14C: raise ProofError(f"not i386: 0x{machine:x}")
        opt=coff+20
        if struct.unpack_from("<H",self.data,opt)[0] != 0x10B: raise ProofError("not PE32")
        if struct.unpack_from("<I",self.data,opt+28)[0] != IMAGE_BASE: raise ProofError("unexpected image base")
        sec=opt+opt_size; self.sections=[]
        for i in range(nsects):
            off=sec+i*40
            name=self.data[off:off+8].split(b"\0",1)[0].decode("ascii","replace")
            vsize,vaddr,raw_size,raw_off=struct.unpack_from("<IIII",self.data,off+8)
            self.sections.append((name,IMAGE_BASE+vaddr,max(vsize,raw_size),raw_off,raw_size))
    def off(self,va:int)->int:
        for _,start,size,raw,raw_size in self.sections:
            if start <= va < start+size:
                d=va-start
                if d>=raw_size: raise ProofError(f"VA 0x{va:x} is not file-backed")
                return raw+d
        raise ProofError(f"unmapped VA 0x{va:x}")
    def bytes(self,va:int,n:int)->bytes:
        o=self.off(va); return self.data[o:o+n]

def expect(pe,va,hexbytes,label):
    want=bytes.fromhex(hexbytes) if isinstance(hexbytes,str) else hexbytes
    got=pe.bytes(va,len(want))
    if got != want: raise ProofError(f"{label} differs at 0x{va:x}: {got.hex()} != {want.hex()}")

def rel32_target(pe,va):
    if pe.bytes(va,1) not in (b"\xe8",b"\xe9"): raise ProofError(f"not rel32 at 0x{va:x}")
    rel=struct.unpack("<i",pe.bytes(va+1,4))[0]
    return va+5+rel

def expect_target(pe,va,target,label):
    got=rel32_target(pe,va)
    if got != target: raise ProofError(f"{label}: 0x{got:x} != 0x{target:x}")

def expect_range_sha(pe,start,end,want,label):
    got=hashlib.sha256(pe.bytes(start,end-start)).hexdigest()
    if got != want: raise ProofError(f"{label} SHA {got} != {want}")

def prove(path:Path)->dict:
    pe=PE(path)
    sha=hashlib.sha256(pe.data).hexdigest()
    if sha != EXPECTED_SHA256: raise ProofError(f"SHA mismatch {sha}")

    # Primary no-parent root helper. numRootBones is read from XModel+0x05 and
    # bounds the bit-mask walk. The whole retained helper is pinned so the
    # proof does not rely on a source-level analogy.
    expect_range_sha(pe,0x8D6100,0x8D621A,
        "d9c24ad6bececdb1bb0ad589cf3ce11abe6e1e5d9156c7db02df19a6833f210e",
        "root no-parent helper")
    expect(pe,0x8D6100,"83ec0c530fb6580503d9","root numRootBones bound")
    expect(pe,0x8D619E,
        "03c6c1e00503442418f7d523d58917"
        "f30f104804f30f1000f30f105008f30f10580c",
        "root mat finalization")

    # Root-with-model-parent helper is independently pinned. It is likewise
    # bounded by XModel+0x05. Its root translation addition is from the supplied
    # parent DObjAnimMat, not from XModel+0x14.
    expect_range_sha(pe,0x8D6220,0x8D6A09,
        "95d74b97dd45e934941f4679deb9ed5c375e03ffea36ec8de3359ee720eb5b1f",
        "root with-parent helper")
    expect(pe,0x8D6220,"81ec940000000fb6490503c8","root-with-parent numRootBones bound")
    expect(pe,0x8D6320,
        "f30f104314f30f584010f30f114010"
        "f30f104318f30f584014f30f114014"
        "f30f10431cf30f584018f30f114018",
        "root parent DObj translation addition")

    # Primary non-root helper. It starts by computing numBones-numRootBones,
    # uses XModel.parentList (+0x0c), and later fetches compact XModel.trans
    # (+0x14), indexed as 3 floats per non-root bone, adding xyz to the animated
    # local translation before parent transform composition.
    expect_range_sha(pe,0x8D6B50,0x8D7212,
        "bf7fdb9128bdc11caa97e0338dd14495d1a4f94c1beab931abbf062c16b014eb",
        "non-root helper")
    expect(pe,0x8D6B50,
        "83ec78558bac24800000000fb645050fb655042bd0",
        "non-root numBones-numRootBones prologue")
    expect(pe,0x8D6C20,
        "8b4d0c894424108bc22b942494000000c1e0050fb62c11",
        "non-root parentList lookup")
    expect(pe,0x8D7016,
        "8bac248c0000008b75148d1452"
        "f30f100496f30f584010f30f114010"
        "f30f10449604f30f584014f30f114014"
        "f30f10449608f30f584018f30f114018",
        "non-root compact bind translation add")

    # Two independent primary skeleton callers have the same architecture:
    # modelParent==0xff -> no-parent root helper; otherwise with-parent helper;
    # then non-root helper starts at minBoneIndex + model->numRootBones.
    expect(pe,0x422A6F,"81faff000000","consumer A modelParent sentinel")
    expect_target(pe,0x422A83,0x8D6100,"consumer A root no-parent")
    expect_target(pe,0x422AC5,0x8D6220,"consumer A root with-parent")
    expect(pe,0x422ACD,"0fb64d05034c2410","consumer A non-root start += numRootBones")
    expect_target(pe,0x422AE2,0x8D6B50,"consumer A non-root")

    expect(pe,0x5C6948,"81f9ff000000","consumer B modelParent sentinel")
    expect_target(pe,0x5C6962,0x8D6100,"consumer B root no-parent")
    expect_target(pe,0x5C69A2,0x8D6220,"consumer B root with-parent")
    expect(pe,0x5C69B3,"0fb64805034c2414","consumer B non-root start += numRootBones")
    expect_target(pe,0x5C69C7,0x8D6B50,"consumer B non-root")

    return {
      "format":"t6-retail-xanim-root-translation-proof-v1",
      "retailExecutable":{"file":path.name,"bytes":len(pe.data),"sha256":sha,"imageBaseHex":"0x00400000"},
      "xmodelX86Offsets":{"numBonesHex":"0x04","numRootBonesHex":"0x05","parentListHex":"0x0c","quatsHex":"0x10","transHex":"0x14"},
      "functions":{
        "CalcSkelRootBonesNoParentOrDuplicateEquivalent":"0x008d6100",
        "CalcSkelRootBonesWithParentEquivalent":"0x008d6220",
        "CalcSkelNonRootBonesEquivalent":"0x008d6b50",
        "primarySkeletonConsumerA":"0x00422a6f",
        "primarySkeletonConsumerB":"0x005c6948"
      },
      "semantics":{
        "ordinaryAnimatedRootTranslation":"XAnim local translation directly; no XModel compact bind-local translation is added for root bones",
        "ordinaryAnimatedNonRootTranslation":"XModel compact bind-local translation + XAnim local translation delta, then parent-space composition",
        "rootWithModelParent":"root animated local transform may be composed with the supplied parent DObj transform, but still does not index XModel.trans[]",
        "deltaPartSeparation":"XAnimParts.deltaPart root motion is a separate already-proven runtime path and is not conflated with ordinary bone-track root translation"
      },
      "validation":{
        "exactRetailSha256":True,
        "rootNoParentWholeFunctionPinned":True,
        "rootWithParentWholeFunctionPinned":True,
        "nonRootWholeFunctionPinned":True,
        "twoPrimaryConsumersMatched":True,
        "rootDoesNotUseCompactModelTrans":True,
        "nonRootCompactBindPlusDeltaMatched":True
      },
      "conclusion":"For ordinary animated bone tracks, T6 uses raw decoded XAnim translation for roots and bind-local XModel.trans + XAnim translation delta for non-roots.",
      "proofBoundary":"Direct static retail-byte proof for the pinned PC executable through the primary DObj root/non-root skeleton composition path. This closes ordinary animated root-bone translation composition. It does not add any claim about unretained executable builds or the separate XAnim binary serialization fixture gate."
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("exe",type=Path); ap.add_argument("--out",type=Path)
    a=ap.parse_args(); doc=prove(a.exe); payload=json.dumps(doc,indent=2,sort_keys=True)+"\n"
    if a.out: a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(payload,encoding="utf-8")
    print(payload,end=""); return 0
if __name__=="__main__": raise SystemExit(main())
