# DDD community data — starter proposal

A draft common HDF5 format for discrete dislocation dynamics, with a small
reference reader and a restart-metadata audit. The intended community resource
accepts uploads only when **every stored snapshot can be continued in the exact
simulation code that produced it**.

This is a discussion seed, not an adopted community standard. The example is
readable and structurally checked, but **not yet demonstrated restartable**.
Schema version: `0.1.0-draft`; expect changes before the first stable release.

## Included

- `examples/loops_mixed_Rz167-edir001-first5.h5`: under 10 MB, with steps
  0, 10, 20, 30 and 40; complete networks at each step; original inputs,
  initial configuration, metadata, and full original run log. Global and timing
  readouts are trimmed through step 40.
- `examples/manifest.json`: a readable copy of `/provenance/manifest_json`.
  Unknown facts are `null`, not inferred. The manifest inside HDF5 is authoritative.
- `ddd_h5.py`: NumPy/h5py reader and draft structural/restart-metadata checks.
- [Format proposal](docs/FORMAT.md), [restart requirements](docs/RESTART.md),
  and [contribution procedure](CONTRIBUTING.md).

## Try it

Python 3.10 or later:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python ddd_h5.py inspect examples/loops_mixed_Rz167-edir001-first5.h5
python ddd_h5.py validate examples/loops_mixed_Rz167-edir001-first5.h5
python -m unittest discover -s tests -v
```

Read one frame without loading the entire trajectory:

```python
from ddd_h5 import Run

with Run("examples/loops_mixed_Rz167-edir001-first5.h5") as run:
    print(run.steps)  # numerical order, not alphabetical HDF5 key order
    frame = run.snapshot(20)
    positions = frame["nodes"]["position"]
    endpoints = frame["segments"][["node1_id", "node2_id"]]
    burgers = frame["segments"]["burgers_vector"]
    time = frame["metadata"]["tottime"]
    provenance = run.manifest
```

The reader preserves source values and units; it does not silently convert units.
Endpoint values are node IDs, not necessarily row indices. It never executes
embedded input scripts or continuation instructions.

## Restart acceptance

```sh
python ddd_h5.py validate --require-restart examples/loops_mixed_Rz167-edir001-first5.h5
```

This command **currently exits with status 1**, deliberately: the supplied legacy
sample lacks native checkpoints, fully pinned source/build information, explicit
physical conventions, and continuation verification evidence. Its input driver
already has a restart pathway, but that alone is not proof that the saved HDF5
state can resume the simulation. Do not use the sample's `example_incomplete`
status for production uploads.

The validator checks metadata and embedded checksums. It does not execute the
simulation, independently verify a claimed successful restart, or certify physical
correctness. Review and reproduce the contributed continuation test separately.

## Repository and dataset roles

Use GitHub for the evolving specification, reader, validators, converter adapters,
issues and this small fixture. Store production trajectories on Hugging Face.
Pin each dataset release to a format version and reader/converter commit. Archive
release versions of code and documentation with Zenodo when ready to publish.

Before a major upload, convert and review one run from the next contributing code.
Resolve physical conventions and prove continuation at every retained frame.

## Rights and publication

Code and data licenses have not yet been selected by the contributors. No blanket
license is assigned to the supplied data or embedded scripts by this draft.
Resolve code and data licensing separately before a public community release.
The example preserves original job logs and paths for provenance.
