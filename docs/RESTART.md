# Continue every stored snapshot

The project target is operational continuation in the generating code. A graph of
nodes and segments is not always the complete simulator state. Preserve internal
integrator history, accumulated plastic deformation, stress/loading-controller
state, time/step, stochastic state, topology information and other solver-owned
state needed by that particular version.

## Initial acceptance profile

1. Include the common analysis representation for every frame.
2. Include the generating simulator's native checkpoint for every frame, byte for
   byte, with a SHA-256 hash. Include every member of multi-file checkpoints.
3. Supply a complete source archive, original repository and full commit, all
   recursive submodule commits and source, and any local/untracked changes that
   affect execution. A top-level commit alone does not identify a dirty build.
   `software.submodules` may explicitly be `{"status":"none"}` if none exist;
   otherwise it maps repository/path to revision. Unknown is not the same as none.
4. Include environment/build instructions and dependency versions. Document the
   compiler, flags, precision, CPU/GPU backend, driver/runtime, thread/rank counts,
   hardware and deterministic/nondeterministic settings. Archive supporting code
   within its applicable redistribution terms.
5. Include a launch recipe and configuration that load that frame, retain its
   physical state, and advance beyond its saved time. Explicitly describe changes
   to stop conditions, paths or output directories. Avoid machine-specific paths
   in the portable recipe; preserve original scripts separately for provenance.
6. Supply a continuation report for **every** stored frame. A successful load alone
   is not sufficient. Record an advance, its environment, checks, tolerances and
   results, and compare with a reference continuation where available.

Shared environment and recipe assets need not be duplicated across frames.
Preserve checkpoint/source bytes within the HDF5 file for this first profile.
Future profiles may support immutable externally archived assets or tested
lossless exporters; the current validator intentionally does not accept those yet.

## Per-frame metadata

`restart["20"]` identifies snapshot step 20 and contains:

- `format`: native checkpoint format and version, including archive layout if any.
- `checkpoint`: embedded payload reference and SHA-256.
- `working_directory`: directory relative to the extracted restart assets.
- `argv`: array of command arguments, with paths relative to that working directory.
- `expected_start_time`: matches the snapshot's physical simulation time.
- `verification`: status, procedure, acceptance criteria, environment,
  result summary and an embedded report payload reference.

Describe how HDF5 payloads are extracted to the recipe's file paths in the recipe
bundle. Never depend on the submitter's local working directory. The validator
does not execute commands or extract archives automatically.

## What a report establishes

Record that the native checkpoint and common frame agree in physical network,
cell, time, loading state and other exported quantities, using specified tolerances.
Record that the continuation advances and that expected boundary/loading settings
are retained. State whether the evidence establishes bitwise, tolerance-based, or
statistical agreement. Chaotic trajectories, parallel reductions and stochastic
events mean exact matching must be demonstrated rather than assumed.

The included audit can check that evidence exists, hashes match and a `passed`
status is declared. It cannot establish that an arbitrary report is truthful or
physically adequate. Independent review/reproduction is part of upload acceptance.

## Status of the seed example

The original HDF5 has a driver with `from_restart`, calls `read_restart`, and passes
the returned restart object to `SimulateNetworkPerf`. The network groups include
fields such as integrator name and next substep sizes. It also records an OpenDiS
working-tree commit, but not a verified remote/submodule/build identity.

The seed does not contain native `.exadis` checkpoint bytes, a complete source or
environment bundle, or executed continuation reports. Reconstructing checkpoints
from these fields may be possible; completeness must be established against the
actual producing code before adopting an exporter. No restart command has been
invented and no continuation experiment has been run for this sample.
