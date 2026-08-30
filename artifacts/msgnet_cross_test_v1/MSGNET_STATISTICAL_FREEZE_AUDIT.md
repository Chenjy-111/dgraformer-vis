# MSGNet Statistical Freeze Audit

Audit date: 2026-08-30  
Scope: statistical sensitivity/freeze audit only; no model inference, website edits, test reselection, hypothesis reselection, primary-result replacement, or file deletion.

## Data lineage and integrity checks

- Numeric sources were limited to `case_evidence.csv`, `relation_evidence_single_scale.csv`, and `relation_evidence_all_scale.csv` under `artifacts/msgnet_cross_test_v1/`.
- The available case/relation evidence artifacts are CSV files (with JSON-encoded fields such as control relation lists); no same-named case/relation JSON artifact was present. No prediction arrays or model runtime files were read.
- Case rows: 2,352 = 126 single-scale hypotheses × 14 tests + 42 all-scale hypotheses × 14 tests.
- Frozen test IDs observed exactly: 0, 214, 428, 642, 857, 1071, 1285, 1499, 1713, 1927, 2142, 2356, 2570, 2784.
- Recomputed primary mean, median, sign counts, exact sign-flip p, and BH q matched the existing relation evidence. Maximum absolute differences were: mean 1.735e-18, median 0.000e+0, sign-flip p 0.000e+0, BH q 0.000e+0.

## Methods frozen for this audit

The formal PRIMARY remains the one-sided exact sign-flip test on mean D with the existing family-wise BH correction (126 single-scale; 42 all-scale). No sensitivity result replaces it.

- Exact sign test: one-sided H1 that the sign/median tendency is positive. Zeros are omitted from the binomial trial count and recorded separately; p = P[Binomial(n_nonzero, 0.5) ≥ n_positive].
- BY sensitivity: Benjamini–Yekutieli applied to the existing/recomputed PRIMARY exact sign-flip raw p values separately within the 126- and 42-hypothesis families.
- Temporal sensitivity: deterministic interleaved subsets fixed solely by frozen-list position, followed by the same one-sided exact sign-flip test and separate BH within each family/subset. Exact sign-test BH was also computed as sensitivity.
- Exact inequalities use p/q < 0.05, matching the requested wording.

## A. Exact sign-test sensitivity (14 tests)

| family | family size | zero-D observations | hypotheses with zero D | minimum nonzero n | raw p < .05 | BH q < .05 | minimum raw p | minimum BH q |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| single-scale | 126 | 0 | 0 | 14 | 27 | 27 | 6.103516e-5 | 0.000334 |
| all-scale | 42 | 0 | 0 | 14 | 14 | 14 | 6.103516e-5 | 0.000214 |

## B. Benjamini–Yekutieli sensitivity on PRIMARY sign-flip p

| family | BY-supported q < .05 | minimum BY q |
|---|---:|---:|
| single-scale | 27 | 0.001811 |
| all-scale | 14 | 0.000924 |

This is dependence-robust multiplicity sensitivity only. The original PRIMARY BH result remains unchanged.

## C. Temporal-separation sensitivity

Subset A IDs (frozen positions 1,3,5,7,9,11,13): **0, 428, 857, 1285, 1713, 2142, 2570**  
Subset B IDs (frozen positions 2,4,6,8,10,12,14): **214, 642, 1071, 1499, 1927, 2356, 2784**

Raw span is fixed at 192 hours for this audit, inferred deterministically from the supplied frozen-design statement that a 214-hour adjacent start gap leaves about 22 hours unused; intervals are represented as `[start, start+191]`. Raw span is not a separate column in the permitted case/relation CSV sources. “Minimum gap” below is the unused gap between raw blocks; start-gap minima are also shown to remove ambiguity.

| subset | raw span | start-gap sequence | minimum start gap | unused-gap sequence | minimum unused gap | overlap count |
|---|---:|---|---:|---|---:|---:|
| A | 192 h | 428/429/428/428/429/428 h | 428 h | 236/237/236/236/237/236 h | 236 h | 0 |
| B | 192 h | 428/429/428/428/429/428 h | 428 h | 236/237/236/236/237/236 h | 236 h | 0 |

### Subset exact sign-flip + BH results

| subset | single-scale BH supported | all-scale BH supported |
|---|---:|---:|
| A | 25 | 14 |
| B | 24 | 12 |

### Subset exact sign-test sensitivity

| subset | family | raw p < .05 | BH q < .05 |
|---|---|---:|---:|
| A | single-scale | 25 | 25 |
| A | all-scale | 13 | 13 |
| B | single-scale | 24 | 24 |
| B | all-scale | 12 | 12 |

The n=7 subset BH results are temporal sensitivity only and are not gates for retaining a 14-test PRIMARY-supported relation.

## D. Stability of the 41 PRIMARY-supported relations

- PRIMARY-supported relations with mean D > 0 in both A and B: **41/41**.
- PRIMARY-supported relations with median D > 0 in both A and B: **41/41**.
- Any subset mean D ≤ 0: **0/41** (none).
- Severe temporal-half direction reversal (a half has both mean D ≤ 0 and median D ≤ 0): **0/41** (none).
- PRIMARY median D ≤ 0: **0/41** (none).
- Exact sign-test BH unsupported among PRIMARY-supported: **0/41**.
- BY unsupported among PRIMARY-supported: **0/41** (none).

The complete 41-row stability table, with every requested primary/sign-test/BY/subset/LOO/bootstrap field, is in `msgnet_supported_sensitivity.csv`.

## E. Audit-only classification

Uniform rules were defined in code without hypothesis/edge names:

1. **DEPENDENCE-SENSITIVE** if PRIMARY BY q is not < .05.
2. Otherwise **STABLE UNDER SENSITIVITY** if 14-test sign-test BH q < .05, both subset means and medians are > 0, LOO minimum mean > 0, and bootstrap mean CI low > 0.
3. Otherwise **MIXED SENSITIVITY**.

| audit-only label | count |
|---|---:|
| STABLE UNDER SENSITIVITY | 41 |
| MIXED SENSITIVITY | 0 |
| DEPENDENCE-SENSITIVE | 0 |

These labels are audit-only and were not written to any production website JSON.

## Final answers

1. **Q1. PRIMARY single-scale BH supported:** 27.
2. **Q2. PRIMARY all-scale BH supported:** 14.
3. **Q3. Sign-test BH supported:** single = 27; all = 14.
4. **Q4. BY supported:** single = 27; all = 14.
5. **Q5. Subset A sign-flip BH supported:** single = 25; all = 14.
6. **Q6. Subset B sign-flip BH supported:** single = 24; all = 12.
7. **Q7. PRIMARY-supported relations with mean D > 0 in both A and B:** 41/41.
8. **Q8. Obvious temporal-half reversal:** No; 0 relation(s) met the predeclared severe-reversal rule. Relations with any nonpositive half mean: 0.
9. **Q9. Severe contradiction across sign tendency or temporal split:** None found. BY non-support is reported separately as dependence sensitivity (0), not treated by itself as a directional contradiction.
10. **Q10. Freeze decision:** Yes—statistics can be frozen for website migration, while preserving the original 14-test sign-flip + BH analysis as PRIMARY and carrying audit-only sensitivity labels only in these audit artifacts.
