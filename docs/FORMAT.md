# Draft HDF5 format 0.1.0

One simulation run per file, variable-size networks stored as per-frame groups.
The common representation supports analysis; native checkpoints preserve the state
needed by the original solver. Both belong in the same submission.

## Layout

```text
/
  @ddd_schema_version = "0.1.0-draft"
  inputs/                         original scripts, parameters, initial state
  provenance/manifest_json        scalar UTF-8 JSON, described below
  global_outputs/
    raw_table                     records with Step and Time, plus named readouts
    ...                           optional arrays aligned to raw_table rows
  snapshots/step_<integer>/
    @step, @tottime
    @H, @origin, @pbc
    nodes                         one-dimensional compound records
    segments                      one-dimensional compound records
    restart_payload               optional uint8 array in incomplete drafts;
                                  required by the initial restart upload profile
    ...                           solver-specific state
  restart_assets/                  embedded recipe/input/environment bundles
  software/                       embedded pinned source bundle
  verification/                   embedded continuation reports
  other_outputs/                  auxiliary logs and measurements
```

`nodes` requires integer `node_id` and float `position[3]`. Constraints are optional
and their encoding must be explained. IDs must be unique within a snapshot;
the manifest must state whether they persist across time or can be reused.

`segments` requires integer `node1_id`, integer `node2_id`, and float
`burgers_vector[3]`. Endpoints must refer to node IDs in that snapshot. An optional
`slip_plane_normal[3]` must have its coordinate frame and interpretation documented.
Do not use node IDs as row offsets without constructing the appropriate mapping.

`H` is a 3-by-3 cell matrix, `origin` a three-vector, and `pbc` a three-vector of
boundary flags. Contributors must state whether cell vectors are rows or columns.
Networks may have different node/segment counts between frames. Do not assume a
fixed mesh. Time is physical simulation time, not wall-clock time.

Global readouts may be more frequent than snapshots. Each row must have an explicit
Step and Time; auxiliary arrays use exactly that row order. Separate auxiliary
tables, such as timing data, carry their own Step/time coordinates. Consumers must
join by step/time, not by assuming equal array lengths across groups.

## Metadata contract

`provenance/manifest_json` is authoritative. A JSON sidecar is for human review and
must match it. The provided example illustrates every initial restart-audit field.

| Field | Required meaning for accepted uploads |
|---|---|
| schema_version | Exact specification version |
| status | `restart_verified` after evidence has been supplied and reviewed |
| run_id | Stable source-run identifier; subsets also list their parent and retained steps |
| contributors | Names, affiliations, identifiers and contact as contributors choose |
| data_license | Explicit data license and attribution requirements |
| conventions | Units and all geometric/tensor conventions below |
| physics | Material, crystal/slip systems, temperature, constants, mobility/force laws, boundaries and loading history |
| numerics | Solver/integrator, tolerances, timesteps, collision/topology/remeshing settings and randomness |
| software | Repository, full commit, exact submodule revisions, dirty-tree status/patches, complete source bundle and build instructions |
| environment | Dependency versions/lock, compiler, flags, backend, hardware and parallelism |
| restart_assets | Checksummed bundle of driver, resolved configuration, environment lock, supporting inputs and recipe |
| restart | Per-snapshot checkpoint, continuation command and verification evidence |

Physics/numerics must contain resolved values, including defaults used at generation
time. Linking only to a script or writing “defaults” is insufficient. Instructions
must declare dimensionful parameters and units. The initial implementation checks
these sections are present; their scientific completeness remains a review task.

`conventions` includes `length_unit`, `time_unit`, `burgers_unit`,
`coordinate_frame`, `cell_matrix_convention`, `segment_direction_convention`,
`periodic_segment_convention`, `node_id_scope`, and `readout_fields`.
Readout definitions include units, tensor ordering, stress/strain measures,
engineering versus tensor shear, and reference frame. Normalized lengths must
identify the physical scale (e.g. Burgers magnitude in metres).

The periodic-segment convention must define how to recover a segment's physical
displacement. If endpoints alone are ambiguous, store image shifts or equivalent
unwrapped information. A minimum-image assumption is not universally sufficient.
The sign of a Burgers vector must be tied to the ordered segment endpoints.

## Native preservation

Store each native checkpoint verbatim as a one-dimensional `uint8` dataset,
optionally gzip-compressed. A multi-file checkpoint can be a deterministic archive;
its manifest states archive format, extraction layout and all required files.
Store shared assets once per file and reference them by absolute HDF5 path.

All payload references have this shape:

```json
{"hdf5_path": "/snapshots/step_20/restart_payload", "sha256": "<64 hexadecimal characters>"}
```

The hash covers decoded bytes (the uint8 contents), not HDF5 compression/chunking.
The containing HDF5 file's hash belongs in an external release manifest to avoid
self-referential hashes. Release manifests also identify the Hugging Face revision,
reader/converter versions and source archive identifiers.

## Draft compatibility and validation scope

The included reader supports this initial compound-record layout and the original
unlabelled lab layout. It is not yet a reader for arbitrary third-party DDD files:
those need converters into this layout. Renaming fields or silently changing units
requires a schema change and explicit migration.

This is a development fixture: its exact physical conventions have not been
independently checked, so unresolved fields remain null and strict upload checks
fail. The validator checks basic shapes, IDs, finite positions, time ordering,
metadata presence and payload hashes. It does not yet enforce every documented
scientific invariant or verify native/common-state equivalence automatically.
