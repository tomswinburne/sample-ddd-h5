"""Draft DDD HDF5 reader and structural/restart-metadata validator.

Reads data only. Embedded scripts and continuation commands are never executed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import h5py
import numpy as np

SCHEMA_VERSION = "0.1.0-draft"


def _plain(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


class Run:
    """Context-managed reader; snapshots are loaded individually."""

    def __init__(self, path):
        self.file = h5py.File(path, "r")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.file.close()

    @property
    def steps(self):
        return sorted(int(g.attrs["step"]) for g in self.file["snapshots"].values())

    @property
    def manifest(self):
        if "provenance/manifest_json" not in self.file:
            return None
        return json.loads(self.file["provenance/manifest_json"].asstr()[()])

    def snapshot(self, step):
        group = self.file[f"snapshots/step_{int(step)}"]
        return {
            "nodes": group["nodes"][...],
            "segments": group["segments"][...],
            "metadata": {k: _plain(v) for k, v in group.attrs.items()},
        }

    def readouts(self):
        return {name: ds[...] for name, ds in self.file["global_outputs"].items()}

    def input_text(self, name):
        """Return an embedded input as text; do not execute it."""
        if "/" in name:
            raise ValueError("Use an immediate dataset name under /inputs")
        return self.file[f"inputs/{name}"].asstr()[()]


def validate(path, require_restart=False):
    """Check structure and restart evidence. Does not run a simulator.

    Restart completeness is a metadata/content check, not independent proof of
    physical or bitwise reproducibility. A submitted verification report must
    be reviewed and the continuation experiment independently repeated.
    """
    errors, warnings, restart_gaps = [], [], []
    result = {"file": str(path), "errors": errors, "warnings": warnings,
              "restart_gaps": restart_gaps}

    def check(condition, message):
        if not condition:
            errors.append(message)

    with Run(path) as run:
        f = run.file
        for name in ("snapshots", "inputs", "global_outputs"):
            check(name in f and isinstance(f[name], h5py.Group), f"Missing group /{name}")
        if errors:
            return {**result, "valid": False, "restart_metadata_complete": False}
        steps, times = [], []
        for name, group in f["snapshots"].items():
            try:
                step = int(group.attrs["step"])
                time = float(group.attrs["tottime"])
                check(name == f"step_{step}", f"{name}: name/step mismatch")
                check(step >= 0 and np.isfinite(time) and time >= 0, f"{name}: invalid step/time")
                steps.append(step)
                times.append((step, time))
                nodes, segments = group["nodes"][...], group["segments"][...]
                check(nodes.ndim == segments.ndim == 1, f"{name}: records must be one-dimensional")
                ids = nodes["node_id"]
                check(ids.dtype.kind in "iu", f"{name}: node IDs must be integers")
                check(len(np.unique(ids)) == len(ids), f"{name}: duplicate node IDs")
                check(nodes["position"].shape == (len(nodes), 3), f"{name}: invalid position shape")
                check(np.isfinite(nodes["position"]).all(), f"{name}: nonfinite positions")
                for field in ("node1_id", "node2_id"):
                    check(segments[field].dtype.kind in "iu", f"{name}: {field} must be integers")
                    check(np.isin(segments[field], ids).all(), f"{name}: dangling {field}")
                burgers = segments["burgers_vector"]
                check(burgers.shape == (len(segments), 3), f"{name}: invalid Burgers-vector shape")
                check(np.isfinite(burgers).all(), f"{name}: nonfinite Burgers vectors")
                if "slip_plane_normal" in (segments.dtype.names or ()):
                    normals = segments["slip_plane_normal"]
                    check(normals.shape == (len(segments), 3) and np.isfinite(normals).all(),
                          f"{name}: invalid slip-plane normals")
                for key, shape in (("H", (3, 3)), ("origin", (3,)), ("pbc", (3,))):
                    check(np.shape(group.attrs.get(key)) == shape, f"{name}: invalid/missing {key}")
                cell = np.asarray(group.attrs["H"], dtype=float)
                check(np.isfinite(cell).all() and abs(np.linalg.det(cell)) > 0,
                      f"{name}: invalid cell")
            except (KeyError, ValueError, TypeError, IndexError) as exc:
                errors.append(f"{name}: unreadable required field ({exc})")
        check(bool(steps), "No snapshots")
        check(len(set(steps)) == len(steps), "Duplicate snapshot steps")
        check(all(b[1] >= a[1] for a, b in zip(sorted(times), sorted(times)[1:])),
              "Snapshot time decreases with step")
        try:
            table = f["global_outputs/raw_table"][...]
            check(table.ndim == 1, "raw_table must be one-dimensional")
            check(np.all(np.diff(table["Step"]) > 0), "Readout steps must strictly increase")
            check(np.isfinite(table["Time"]).all() and np.all(np.diff(table["Time"]) >= 0),
                  "Invalid readout times")
            for name, ds in f["global_outputs"].items():
                check(ds.shape and ds.shape[0] == len(table), f"{name}: readout length mismatch")
        except (KeyError, ValueError, TypeError) as exc:
            errors.append(f"Invalid global readouts ({exc})")

        manifest = run.manifest
        if manifest is None:
            warnings.append("Legacy file: no draft manifest")
            restart_gaps.append("Missing provenance/manifest_json")
        else:
            check(isinstance(manifest, dict), "Manifest must be an object")
            if isinstance(manifest, dict):
                _audit_restart(f, manifest, steps, restart_gaps)
                check(manifest.get("schema_version") == SCHEMA_VERSION, "Unsupported manifest schema version")
                if manifest.get("status") != "restart_verified":
                    warnings.append("Example/draft file; not a verified continuation dataset")
        result.update(snapshot_count=len(steps), steps=sorted(steps),
                      restart_metadata_complete=not restart_gaps)
    result["valid"] = not errors and (not require_restart or not restart_gaps)
    return result


def _audit_restart(f, m, steps, gaps):
    """Deliberately conservative draft upload gate; see docs/RESTART.md."""
    def required(value, label):
        if value is None or value == "" or value == [] or value == {}:
            gaps.append(f"Missing {label}")
            return False
        return True

    def payload(spec, label):
        if not isinstance(spec, dict):
            gaps.append(f"Missing {label}")
            return
        path, digest = spec.get("hdf5_path"), spec.get("sha256")
        if not isinstance(path, str) or not path.startswith("/") or path not in f:
            gaps.append(f"{label}: missing embedded payload")
            return
        ds = f[path]
        if not isinstance(ds, h5py.Dataset) or ds.dtype != np.dtype("uint8") or ds.ndim != 1:
            gaps.append(f"{label}: payload must be a one-dimensional uint8 dataset")
            return
        h = hashlib.sha256()
        for start in range(0, len(ds), 1024 * 1024):
            h.update(ds[start:start + 1024 * 1024].tobytes())
        if digest != h.hexdigest() or len(ds) == 0:
            gaps.append(f"{label}: empty payload or SHA-256 mismatch")

    required(m.get("run_id"), "run_id")
    for key in ("contributors", "data_license", "conventions", "physics", "numerics"):
        required(m.get(key), key)
    conventions = m.get("conventions") or {}
    for key in ("length_unit", "time_unit", "burgers_unit", "coordinate_frame", "cell_matrix_convention",
                "segment_direction_convention", "periodic_segment_convention", "node_id_scope", "readout_fields"):
        required(conventions.get(key), f"conventions.{key}")
    software = m.get("software") or {}
    for key in ("name", "repository", "commit", "submodules", "working_tree_status", "build_instructions"):
        required(software.get(key), f"software.{key}")
    if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", str(software.get("commit", ""))):
        gaps.append("software.commit must be a full commit identifier")
    payload(software.get("source_bundle"), "software.source_bundle")
    environment = m.get("environment") or {}
    for key in ("dependencies", "compiler", "build_flags", "backend", "hardware", "parallelism"):
        required(environment.get(key), f"environment.{key}")
    payload(m.get("restart_assets"), "restart_assets")
    records = m.get("restart") or {}
    if set(records) != {str(s) for s in steps}:
        gaps.append("restart must have exactly one entry for every stored snapshot step")
    for step in steps:
        rec = records.get(str(step)) or {}
        payload(rec.get("checkpoint"), f"step {step} checkpoint")
        for key in ("format", "working_directory", "argv", "expected_start_time", "verification"):
            required(rec.get(key), f"step {step} {key}")
        argv = rec.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            gaps.append(f"step {step}: argv must be a nonempty array of strings")
        if rec.get("expected_start_time") != float(f[f"snapshots/step_{step}"].attrs["tottime"]):
            gaps.append(f"step {step}: expected_start_time differs from snapshot")
        verification = rec.get("verification") or {}
        if verification.get("status") != "passed":
            gaps.append(f"step {step}: continuation verification has not passed")
        for key in ("procedure", "acceptance_criteria", "environment", "result_summary"):
            required(verification.get(key), f"step {step} verification.{key}")
        payload(verification.get("report"), f"step {step} verification.report")
    if m.get("status") != "restart_verified":
        gaps.append("Manifest status is not restart_verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "validate"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--require-restart", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            with Run(args.file) as run:
                print(json.dumps({"steps": run.steps, "manifest": run.manifest}, indent=2))
            return 0
        report = validate(args.file, args.require_restart)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        report = {"valid": False, "errors": [str(exc)]}
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
