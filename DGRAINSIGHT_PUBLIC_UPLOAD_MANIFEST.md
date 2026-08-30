# DGraInsight Public Upload Manifest

Audit date: 2026-08-31

## TO_COMMIT

- Current Python source: `dgraudit/`, including Config v2, Session v2, validators, native Quick Inspection v2, Formal Audit v2, and the DGraFormer/MSGNet/MTGNN adapters.
- Current CLI and launch helpers: `dgraudit/__main__.py`, `dgraudit/cli/`, `Start-DGraInsight-Audit.cmd`, and `Start-DGraInsight-Audit.ps1`.
- Current configurations and schema: `configs/` and `schemas/dgrainsight_audit_session_v2.schema.json`.
- Frozen public formal operands: `artifacts/dgraformer_frozen40/` and `artifacts/msgnet_frozen14/`.
- Current graph and Session v2 fixtures: `tests/fixtures/`.
- Current Web v2 source and built-in evidence assets: `src/` and `public/`.
- Current regression tests: Python tests under `tests/test_*.py` and Web tests under `tests/*.mjs`.
- Reproducibility and user documentation: `README.md`, `docs/`, requirements, npm lockfile, TypeScript configuration, and Vite configuration.
- Repository hygiene and audit records: `.gitignore`, `V1_REMOVAL_DEPENDENCY_AUDIT.md`, `DGRAINSIGHT_V1_REMOVAL_MANIFEST.md`, `DGRAINSIGHT_V1_SAFE_REMOVAL_REPORT.md`, this manifest, and `DGRAINSIGHT_PUBLIC_REPOSITORY_AUDIT.md`.
- The staged tracked-only candidate contains 2,612 files after adding the repository audit. All current v2 files required by the final gates are included.

## DO_NOT_COMMIT

- `.env`, `.env.*`, tokens, API keys, credentials, private keys, and machine-local settings.
- Private/raw datasets, local checkpoints, and upstream source trees with unresolved redistribution terms.
- `.venv/`, `.tmp/`, `tmp/`, `node_modules/`, `scripts/node_modules/`, `dist/`, Python caches, TypeScript build info, logs, and editor/OS metadata.
- Generated user sessions, temporary audit configs, local experiment output, backup copies, and interrupted/final verification snapshots.
- `third_party/`, `artifacts/msgnet_checkpoints/`, `artifacts/mtgnn_exchange/`, `artifacts/preflight/`, and other ignored local-only resources.

## LARGE_FILES

Tracked files larger than 10 MiB:

| File | Size | Disposition |
|---|---:|---|
| `public/data/evidence/msgnet_etth1_session_v2.json` | 73.29 MiB | Required public built-in Session v2 asset; below GitHub's 100 MiB per-file limit. |
| `public/data/evidence/dgraformer_etth1_session_v2.json` | 15.94 MiB | Required public built-in Session v2 asset. |

- Files larger than 100 MiB: **none**.
- Unexpected oversized files: **none**.

## EXTERNAL/PRIVATE RESOURCES

- Raw DGraFormer/MSGNet/MTGNN datasets are external and are not committed.
- User checkpoints are external/private and are not committed.
- Upstream model source directories are external; `DGRAINSIGHT_MSGNET_SOURCE` may point the optional MSGNet helper to a local checkout.
- Reproducing live Quick Inspection requires users to supply their own authorized model source, checkpoint, and dataset. Frozen public Formal Audit operands and built-in Session v2 evidence remain in the repository.
- No required current-v2 file is ignored; ignored files are generated caches, installed dependencies, build products, verification copies, or external/private resources.

## RELEASE_METADATA_PENDING

- Owner-approved `LICENSE` selection.
- Verified `CITATION.cff` and author/affiliation metadata.
- Optional release tag, release notes, DOI/archive metadata, and final GitHub repository description/topics.
- User approval to commit and push. No commit, push, remote change, or GitHub Release was performed by this audit.
