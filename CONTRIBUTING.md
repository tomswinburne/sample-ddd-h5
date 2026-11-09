# Contributing a run or simulator adapter

Start with one small representative run before converting a large campaign.

1. Identify the simulator and exact code version, and list all native checkpoint
   files needed to resume one saved frame.
2. Write a converter into the draft network layout. Preserve source precision,
   attributes and native checkpoints; record converter source/version/options.
3. Fill the manifest with resolved parameters, conventions and provenance.
   Unknown values stay null during development and block release acceptance.
4. Load the result with the common reader. Check geometry and tensor conventions
   against the original simulator, including periodic segments and Burgers signs.
5. Reproduce the continuation recipe for every stored snapshot and archive the
   reports. Supply source/build/input bundles and payload checksums.
6. Run `python ddd_h5.py validate --require-restart your-run.h5` and review the
   physical semantics the draft validator cannot yet enforce.
7. Review authorship, attribution and code/data licenses with the contributors.
8. Upload production files to the shared dataset repository, with a run index,
   checksums, pinned reader/converter versions and a versioned dataset card.

This repository contains a single small fixture for development. Large production
uploads belong on the dataset host, not in Git history. An upload process should
run strict checks before accepting files; no Hugging Face upload automation is
implemented in this starter.

The first cross-code collaboration should settle ambiguous conventions in the
specification and add an independent fixture/adapter before declaring version 1.0.
