# DGraInsight Public Repository Audit

Audit date: 2026-08-31

## Decision

**PUBLIC REPOSITORY READY FOR USER APPROVAL**

## Required answers

- Current v2 complete and reproducible: **YES**. The tracked-only candidate contains current source, Config v2, Session v2 schema/validators, frozen formal operands, current fixtures, Web assets, tests, README, and reproducibility documentation.
- Required ignored file: **NO**. The tracked-only copy contained exactly all 2,611 files staged before this report was added and passed every required gate; this report is the only newly added file afterward.
- Private/secret file: **NO** in the commit candidate. Secret-pattern, sensitive-filename, checkpoint/database, and local absolute-path scans returned zero publishable-candidate findings. External datasets, checkpoints, local environments, and upstream source trees remain ignored.
- Unexpected oversized file: **NO**. The only files over 10 MiB are the required MSGNet Session v2 asset (73.29 MiB) and DGraFormer Session v2 asset (15.94 MiB). No file exceeds 100 MiB.
- Web build: **PASS**. TypeScript compile, Session v2 Web regression, graph Web regression, and Vite production build passed in the tracked-only copy.
- Graph regression: **PASS** for DGraFormer, MSGNet, and MTGNN; protected graph cores and baseline predictions remain unchanged.
- Formal CLI / Session v2: **PASS**. The immediately preceding V1 Safe Removal Formal CLI reproduction remains the frozen baseline; this audit did not repeat the large formal computation. Both public Formal Session v2 assets were revalidated successfully in the tracked-only copy.
- Legacy runtime: **NO**. Session v1 inference = 0; empirical-p computation runtime = 0; old case-level BH runtime = 0; B=100 significance runtime = 0. Legacy field names occur only in explicit fail-closed validators and negative regression assertions.
- README current-version description: **PASS**. README identifies the repository as v2-only and describes Config v2, Quick Inspection v2, Formal Audit v2, and Session v2 as current.
- Safe to upload to GitHub: **YES, after user approval**. Technical and repository-hygiene gates pass. Owner-controlled license/citation/release metadata remains listed as pending and no upload action has been taken.

## Final gate record

- Git candidate before this report: 2,611 tracked files, 0 untracked files, 0 unstaged files.
- Tracked-only fresh copy: 2,611/2,611 files at `.tmp/public-upload-audit-20260831`.
- Python: 38/38 tests PASS using the preserved Python 3.9/PyTorch environment; no dependency download or training.
- Session v2 validation: DGraFormer PASS; MSGNet PASS.
- Web Session v2 validation: PASS.
- Web graph regression: DGraFormer, MSGNet, and MTGNN PASS.
- TypeScript/Vite production build: PASS.
- Git action: no commit, no push, no release, no remote modification.
