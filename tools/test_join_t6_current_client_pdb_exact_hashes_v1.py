#!/usr/bin/env python3
from __future__ import annotations
import csv,json,subprocess,sys,tempfile,unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SCRIPT=HERE/"join_t6_current_client_pdb_exact_hashes_v1.py"

def write_tsv(path,fields,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,dialect="excel-tab",lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

class ExactHashJoinTests(unittest.TestCase):
    def test_unique_hash_promotes_and_duplicate_stays_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            catalog=root/"catalog.tsv"
            pdb=root/"pdb.tsv"
            out=root/"join.json"
            cy=root/"cypher"
            write_tsv(catalog,[
                "entry_va","instruction_bytes_sha256","name"
            ],[
                {"entry_va":"00401000","instruction_bytes_sha256":"aa"*32,"name":"FUN_00401000"},
                {"entry_va":"00402000","instruction_bytes_sha256":"bb"*32,"name":"FUN_00402000"},
                {"entry_va":"00403000","instruction_bytes_sha256":"cc"*32,"name":"FUN_00403000"},
            ])
            write_tsv(pdb,[
                "exact_bytes_sha256","variant_id","family_id","symbol_name","object_name",
                "exact_address_start","exact_size_bytes"
            ],[
                {"exact_bytes_sha256":"aa"*32,"variant_id":"urn:test:variant:unique",
                 "family_id":"urn:test:family:unique","symbol_name":"UniqueFn","object_name":"unique.obj",
                 "exact_address_start":"0x1000","exact_size_bytes":"32"},
                {"exact_bytes_sha256":"bb"*32,"variant_id":"urn:test:variant:dup1",
                 "family_id":"urn:test:family:dup1","symbol_name":"DupFn1","object_name":"dup.obj",
                 "exact_address_start":"0x2000","exact_size_bytes":"16"},
                {"exact_bytes_sha256":"bb"*32,"variant_id":"urn:test:variant:dup2",
                 "family_id":"urn:test:family:dup2","symbol_name":"DupFn2","object_name":"dup.obj",
                 "exact_address_start":"0x3000","exact_size_bytes":"16"},
            ])
            p=subprocess.run([
                sys.executable,str(SCRIPT),
                "--catalog",str(catalog),
                "--pdb-hashes",str(pdb),
                "--out",str(out),
                "--cypher-out-dir",str(cy),
                "--chunk-size","2",
            ],check=True,capture_output=True,text=True)
            self.assertTrue(p.stdout.strip())
            doc=json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(doc["current_client_catalog_functions"],3)
            self.assertEqual(doc["server_pdb_exact_hash_variants"],3)
            self.assertEqual(doc["match_rows"],3)
            self.assertEqual(doc["current_client_functions_with_match"],2)
            self.assertEqual(doc["ambiguous_current_client_hashes"],1)

            manifest=json.loads((cy/"manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["acceptedRows"],1)
            self.assertEqual(manifest["candidateAmbiguousRows"],2)
            self.assertEqual(manifest["matchRows"],3)

            joined="\n".join(p.read_text(encoding="utf-8") for p in sorted(cy.glob("matches_*.cypher")))
            self.assertIn("CROSSBUILD_CORRESPONDS_TO",joined)
            self.assertIn("accepted-exact-byte-identity-witness",joined)
            self.assertIn("candidate-ambiguous-exact-byte-hash",joined)
            self.assertIn("CASE WHEN row.accepted THEN [1] ELSE [] END",joined)

            # The no-hit client function must not appear in graph projection.
            self.assertNotIn("00403000",joined.lower())

    def test_evidence_ids_are_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            catalog=root/"catalog.tsv"
            pdb=root/"pdb.tsv"
            write_tsv(catalog,["entry_va","instruction_bytes_sha256","name"],[
                {"entry_va":"00401000","instruction_bytes_sha256":"dd"*32,"name":"FUN_00401000"},
            ])
            write_tsv(pdb,[
                "exact_bytes_sha256","variant_id","family_id","symbol_name","object_name",
                "exact_address_start","exact_size_bytes"
            ],[
                {"exact_bytes_sha256":"dd"*32,"variant_id":"urn:test:variant:x",
                 "family_id":"urn:test:family:x","symbol_name":"X","object_name":"x.obj",
                 "exact_address_start":"0x1000","exact_size_bytes":"7"},
            ])
            contents=[]
            for i in range(2):
                out=root/f"join{i}.json"
                cy=root/f"cy{i}"
                subprocess.run([
                    sys.executable,str(SCRIPT),
                    "--catalog",str(catalog),
                    "--pdb-hashes",str(pdb),
                    "--out",str(out),
                    "--cypher-out-dir",str(cy),
                ],check=True,capture_output=True,text=True)
                contents.append((cy/"matches_0000.cypher").read_text(encoding="utf-8"))
            self.assertEqual(contents[0],contents[1])

if __name__=="__main__":
    unittest.main()
