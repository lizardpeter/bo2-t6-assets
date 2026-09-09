#!/usr/bin/env python3
"""Derive the retail T6 DObj modelParent *application* rule fail-closed.

This adapter intentionally does not attempt to prove how DObj construction
assigns modelParent, model order, duplicate bone-name precedence, or how an
XAnim channel absent from the assembled DObj is handled.  It derives only the
runtime transform-application rule already witnessed by the exact retail
skeleton consumers and helper bodies in the pinned root-translation proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_RETAIL_SHA256 = "11c7542fc571379da5b3dbb8967372c2f8283e8457ae4a78070e16d51824d5d1"
UPSTREAM_MANIFEST = Path("manifests/xanim/T6_RETAIL_XANIM_ROOT_TRANSLATION_PROOF_V1.json")
UPSTREAM_VERIFIER = Path("tools/t6_retail_xanim_root_translation_proof_v1.py")
EXPECTED_MANIFEST_BLOB_SHA1 = "c30595cf22f98644605513f34cfa404cae30aa4c"
EXPECTED_VERIFIER_BLOB_SHA1 = "8602765f4c5ea3e6a95037dbb26fe20665441f45"


class ProofError(RuntimeError):
    pass


def git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProofError(message)


def prove(repo_root: Path) -> dict:
    manifest_path = repo_root / UPSTREAM_MANIFEST
    verifier_path = repo_root / UPSTREAM_VERIFIER
    manifest_bytes = manifest_path.read_bytes()
    verifier_bytes = verifier_path.read_bytes()

    manifest_blob = git_blob_sha1(manifest_bytes)
    verifier_blob = git_blob_sha1(verifier_bytes)
    require(
        manifest_blob == EXPECTED_MANIFEST_BLOB_SHA1,
        f"upstream manifest blob drifted: {manifest_blob}",
    )
    require(
        verifier_blob == EXPECTED_VERIFIER_BLOB_SHA1,
        f"upstream verifier blob drifted: {verifier_blob}",
    )

    upstream = json.loads(manifest_bytes.decode("utf-8"))
    require(
        upstream.get("format") == "t6-retail-xanim-root-translation-proof-v1",
        "unexpected upstream proof format",
    )
    retail = upstream.get("retailExecutable", {})
    require(retail.get("bytes") == 12850328, "retail byte-size pin drifted")
    require(retail.get("sha256") == EXPECTED_RETAIL_SHA256, "retail SHA-256 pin drifted")

    functions = upstream.get("functions", {})
    require(
        functions == {
            "CalcSkelNonRootBonesEquivalent": "0x008d6b50",
            "CalcSkelRootBonesNoParentOrDuplicateEquivalent": "0x008d6100",
            "CalcSkelRootBonesWithParentEquivalent": "0x008d6220",
            "primarySkeletonConsumerA": "0x00422a6f",
            "primarySkeletonConsumerB": "0x005c6948",
        },
        "upstream retail function witness set drifted",
    )

    validation = upstream.get("validation", {})
    for key in (
        "exactRetailSha256",
        "rootNoParentWholeFunctionPinned",
        "rootWithParentWholeFunctionPinned",
        "twoPrimaryConsumersMatched",
    ):
        require(validation.get(key) is True, f"required upstream gate is not true: {key}")

    semantics = upstream.get("semantics", {})
    require(
        semantics.get("rootWithModelParent")
        == "root animated local transform may be composed with the supplied parent DObj transform, but still does not index XModel.trans[]",
        "upstream rootWithModelParent semantic statement drifted",
    )

    return {
        "format": "t6-retail-dobj-model-parent-application-proof-v1",
        "retailExecutable": {
            "bytes": 12850328,
            "sha256": EXPECTED_RETAIL_SHA256,
        },
        "upstreamAuthority": {
            "manifest": UPSTREAM_MANIFEST.as_posix(),
            "manifestGitBlobSha1": manifest_blob,
            "verifier": UPSTREAM_VERIFIER.as_posix(),
            "verifierGitBlobSha1": verifier_blob,
        },
        "retailWitnesses": {
            "primarySkeletonConsumerA": "0x00422a6f",
            "primarySkeletonConsumerB": "0x005c6948",
            "rootNoParentHelper": "0x008d6100",
            "rootWithParentHelper": "0x008d6220",
        },
        "proven": {
            "modelParentSentinel": (
                "In two independent primary retail skeleton consumers, modelParent == 0xFF "
                "selects the no-model-parent root path."
            ),
            "modelParentNonSentinel": (
                "In those consumers, non-0xFF modelParent selects the separately pinned "
                "root-with-model-parent helper."
            ),
            "rootParentTranslationApplication": (
                "The pinned root-with-model-parent helper adds the supplied parent DObj "
                "translation to animated root translation."
            ),
        },
        "notProven": [
            "DObj multi-XModel assembly order",
            "how modelParent is assigned during DObj construction",
            "attachment-model parent selection",
            "duplicate ScriptString bone precedence",
            "behavior for animation ScriptStrings absent from the assembled DObj, including j_mms_flip",
        ],
        "proofBoundary": (
            "Derived only from the immutable retail root-translation authority above. "
            "This closes runtime application of an already-supplied modelParent value; it "
            "does not close DObj construction or XAnim-to-DObj name resolution."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    doc = prove(args.repo_root.resolve())
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
