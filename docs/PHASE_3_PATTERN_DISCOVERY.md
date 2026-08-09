# Phase 3 Candidate Pattern Discovery

## Result

Candidate patterns were computed deterministically from the real Phase 2 Top-K masks and pre-Top-K scores. Every reported pattern carries the exact label `Candidate Pattern` and claim level `structural_candidate`.

No pattern is described as important, causal, true, or prediction-influential.

## Definitions

- Persistent edge: retained in all seven windows.
- Window-specific edge: retained in exactly one window.
- High-weight/low-frequency edge: mean retained score at or above the dataset Q3 and frequency at or below Q1.
- High-frequency/low-weight edge: frequency at or above Q3 and mean retained score at or below Q1.
- Sender/receiver role: outgoing/incoming retained occurrence count at or above the dataset Q3.
- Repeated local edge set: a directed two-edge set co-occurring in at least two windows; at most 25 sets are reported per dataset in deterministic order.

## Candidate counts

| Dataset | Persistent | Window-specific | High-weight / low-frequency | High-frequency / low-weight | Sender | Receiver | Repeated sets |
|---|---:|---:|---:|---:|---:|---:|---:|
| ETTh1 | 0 | 12 | 3 | 3 | 2 | 3 | 25 |
| ETTh2 | 0 | 14 | 4 | 3 | 2 | 2 | 25 |
| ETTm1 | 0 | 11 | 3 | 0 | 2 | 2 | 25 |
| ETTm2 | 0 | 16 | 7 | 6 | 2 | 2 | 25 |
| Weather | 0 | 144 | 55 | 40 | 6 | 6 | 25 |

Zero persistent edges is a valid computed result for the supplied checkpoints; no placeholder was substituted.

## Evidence retained per edge

Each retained-edge record includes source/target indices and names, retained windows, frequency, mean score, plus for every window:

- score before Top-K;
- retained state;
- rank among all `N × N` slots;
- off-diagonal rank;
- actual Top-K boundary score;
- score minus boundary.

## Reproduction

- Run ID: `467d53169372e3120e7964f81152bee863fc5ef121b01e5413ed813c14c10a5c`
- Upstream graph run: `bc60c5a9f09c46d5e176a2e014bb7b516c7c562270f86c31bb382ee48342175b`
- Configuration: `configs/pattern_discovery.json`
- Results: `artifacts/runs/<run_id>/patterns/*.json`
- Manifest, command, environment, stdout and stderr are stored in the run directory.

## Missing cross-run evidence

Cross-run repeated patterns are explicitly stored with `status: missing`, because only one checkpoint is available per dataset. They are not estimated from windows and are not replaced with randomized runs.

## Scientific boundary

These are structural candidate patterns in the supplied model graphs. Phase 3 does not establish prediction influence. A candidate must pass real checkpoint intervention and matched controls before a stronger model-internal evidence claim is allowed.
