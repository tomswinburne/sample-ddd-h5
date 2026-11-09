import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from ddd_h5 import Run, validate

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/loops_mixed_Rz167-edir001-first5.h5"


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "example.h5"
        shutil.copyfile(EXAMPLE, self.path)

    def test_example_is_small_and_readable(self):
        self.assertLess(EXAMPLE.stat().st_size, 10_000_000)
        with Run(EXAMPLE) as run:
            self.assertEqual(run.steps, [0, 10, 20, 30, 40])
            frame = run.snapshot(20)
            self.assertEqual(frame["nodes"]["position"].shape[1], 3)
            self.assertEqual(len(run.readouts()["raw_table"]), 40)
            self.assertIn("from_restart", run.input_text("strainhard_py"))
        self.assertTrue(validate(EXAMPLE)["valid"])

    def test_example_does_not_claim_restart_readiness(self):
        report = validate(EXAMPLE, require_restart=True)
        self.assertFalse(report["valid"])
        self.assertFalse(report["restart_metadata_complete"])
        self.assertTrue(any("step 40 checkpoint" in x for x in report["restart_gaps"]))

    def test_dangling_endpoint_is_rejected(self):
        with h5py.File(self.path, "r+") as f:
            ds = f["snapshots/step_20/segments"]
            record = ds[0]
            record["node1_id"] = 2_000_000_000
            ds[0] = record
        report = validate(self.path)
        self.assertFalse(report["valid"])
        self.assertTrue(any("dangling node1_id" in x for x in report["errors"]))

    def test_nonfinite_position_is_rejected(self):
        with h5py.File(self.path, "r+") as f:
            ds = f["snapshots/step_0/nodes"]
            record = ds[0]
            record["position"][0] = np.nan
            ds[0] = record
        self.assertFalse(validate(self.path)["valid"])

    def test_missing_required_field_is_reported(self):
        with h5py.File(self.path, "r+") as f:
            del f["snapshots/step_10/nodes"]
        self.assertFalse(validate(self.path)["valid"])

    def test_readout_alignment_is_checked(self):
        with h5py.File(self.path, "r+") as f:
            del f["global_outputs/S"]
            f.create_dataset("global_outputs/S", data=np.zeros((3, 3, 3)))
        self.assertFalse(validate(self.path)["valid"])

    def test_manifest_sidecar_matches(self):
        with Run(EXAMPLE) as run:
            sidecar = json.loads((EXAMPLE.parent / "manifest.json").read_text())
            self.assertEqual(run.manifest, sidecar)

    def _synthetic_complete_metadata(self):
        """Fake payloads exercise audit logic; never assert a real restart occurred."""
        with h5py.File(self.path, "r+") as f:
            m = json.loads(f["provenance/manifest_json"].asstr()[()])
            data = b"Synthetic unit-test payload, NOT a simulator checkpoint."
            f.create_dataset("test_payload", data=np.frombuffer(data, dtype=np.uint8))
            ref = {"hdf5_path": "/test_payload", "sha256": hashlib.sha256(data).hexdigest()}
            m.update(status="restart_verified", contributors=["Test"], data_license="Test-only",
                     physics={"fixture": True}, numerics={"fixture": True}, restart_assets=ref)
            m["conventions"] = {k: "Test-only" for k in m["conventions"]}
            m["software"].update(repository="https://example.invalid/test", submodules={"status": "none"},
                                 working_tree_status="clean", build_instructions="Test-only", source_bundle=ref)
            m["environment"] = {k: "Test-only" for k in m["environment"]}
            for rec in m["restart"].values():
                rec.update(format="synthetic", checkpoint=ref, working_directory=".", argv=["not-executed"])
                rec["verification"] = dict(status="passed", procedure="synthetic fixture",
                    acceptance_criteria="unit test only", environment="synthetic", result_summary="synthetic",
                    report=ref)
            f["provenance/manifest_json"][()] = json.dumps(m)

    def test_complete_metadata_and_hash_tampering(self):
        self._synthetic_complete_metadata()
        self.assertTrue(validate(self.path, require_restart=True)["valid"])
        with h5py.File(self.path, "r+") as f:
            f["test_payload"][0] = 0
        report = validate(self.path, require_restart=True)
        self.assertFalse(report["valid"])
        self.assertTrue(any("SHA-256 mismatch" in x for x in report["restart_gaps"]))

    def test_every_frame_needs_a_restart_record(self):
        self._synthetic_complete_metadata()
        with h5py.File(self.path, "r+") as f:
            m = json.loads(f["provenance/manifest_json"].asstr()[()])
            del m["restart"]["30"]
            f["provenance/manifest_json"][()] = json.dumps(m)
        self.assertFalse(validate(self.path, require_restart=True)["valid"])


if __name__ == "__main__":
    unittest.main()
