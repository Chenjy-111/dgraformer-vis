# Corrected-Supported Candidate Outlier Sensitivity

This analysis reads existing paired-effect CSV files only. It does not run model inference and does not alter the formal V2 results or BH families.

## Local w6 0->4

- Active: 28/40
- min / max D: -0.0024262671 / +0.0040089187
- mean / median D: +0.0009624545 / +0.0001852158
- sample SD: 0.0017159087
- Q1 / Q3: -0.0003163702 / +0.0021975339
- 10% trimmed mean: +0.0009245135 (removed 2 from each tail)
- Mean after removing largest positive D: +0.0008496225
- Mean after removing two largest positive D: +0.0007294985
- D>0: 17/28 (60.7%)
- Trimmed-mean L=3 block p: 0.005299470053
- Trimmed-mean block CI95: [+0.0002895460, +0.0016411344]
- Median L=3 block CI95: [-0.0001263241, +0.0020206909]
- Median block p: not reported (non-smooth statistic with varying active counts; CI retained).
- Classification: SOMEWHAT OUTLIER-SENSITIVE
- Basis: top-1/top-2 removal and trimming preserve a positive effect, but not every robust criterion is satisfied.

| Rank | Sample | D |
|---:|---:|---:|
| 1 | 2070 | -0.0024262671 |
| 2 | 1285 | -0.0007950950 |
| 3 | 2570 | -0.0007049458 |
| 4 | 1642 | -0.0006590205 |
| 5 | 571 | -0.0005701744 |
| 6 | 1570 | -0.0004061198 |
| 7 | 999 | -0.0003375099 |
| 8 | 1142 | -0.0003093236 |
| 9 | 2284 | -0.0002259128 |
| 10 | 1785 | -0.0001263241 |
| 11 | 500 | -0.0000865681 |
| 12 | 1071 | +0.0000241009 |
| 13 | 642 | +0.0000457279 |
| 14 | 928 | +0.0000901181 |
| 15 | 2784 | +0.0002803135 |
| 16 | 71 | +0.0008807548 |
| 17 | 143 | +0.0012500247 |
| 18 | 2142 | +0.0015607817 |
| 19 | 1499 | +0.0019248049 |
| 20 | 1428 | +0.0020206909 |
| 21 | 2498 | +0.0020466863 |
| 22 | 1927 | +0.0026500768 |
| 23 | 785 | +0.0028035302 |
| 24 | 286 | +0.0031564386 |
| 25 | 1999 | +0.0034352734 |
| 26 | 2641 | +0.0034449000 |
| 27 | 428 | +0.0039728456 |
| 28 | 2427 | +0.0040089187 |

## Global 0->2

- Active: 28/40
- min / max D: -0.0015334913 / +0.0061873552
- mean / median D: +0.0012460001 / +0.0011586056
- sample SD: 0.0017030052
- Q1 / Q3: +0.0003029246 / +0.0020929173
- 10% trimmed mean: +0.0011332508 (removed 2 from each tail)
- Mean after removing largest positive D: +0.0010629870
- Mean after removing two largest positive D: +0.0009331716
- D>0: 22/28 (78.6%)
- Trimmed-mean L=3 block p: 0.000199980002
- Trimmed-mean block CI95: [+0.0006297644, +0.0016503569]
- Median L=3 block CI95: [+0.0006061601, +0.0015048210]
- Median block p: not reported (non-smooth statistic with varying active counts; CI retained).
- Classification: ROBUST
- Basis: positive after top-1/top-2 removal, trimmed-mean p<.05, and median block CI entirely above zero.

| Rank | Sample | D |
|---:|---:|---:|
| 1 | 857 | -0.0015334913 |
| 2 | 1856 | -0.0014020671 |
| 3 | 357 | -0.0011407080 |
| 4 | 2427 | -0.0006651608 |
| 5 | 1356 | -0.0003756397 |
| 6 | 1285 | -0.0001600902 |
| 7 | 1642 | +0.0002937934 |
| 8 | 2356 | +0.0003059683 |
| 9 | 2142 | +0.0005519373 |
| 10 | 642 | +0.0006061601 |
| 11 | 0 | +0.0007888089 |
| 12 | 1785 | +0.0008659754 |
| 13 | 1927 | +0.0011034679 |
| 14 | 785 | +0.0011460247 |
| 15 | 500 | +0.0011711866 |
| 16 | 2284 | +0.0012380174 |
| 17 | 999 | +0.0014053746 |
| 18 | 2498 | +0.0014386361 |
| 19 | 286 | +0.0015048210 |
| 20 | 143 | +0.0015932032 |
| 21 | 428 | +0.0019471661 |
| 22 | 1999 | +0.0025301709 |
| 23 | 1428 | +0.0025400684 |
| 24 | 1142 | +0.0025707035 |
| 25 | 2641 | +0.0026720164 |
| 26 | 1499 | +0.0032661174 |
| 27 | 2784 | +0.0044381886 |
| 28 | 928 | +0.0061873552 |

## Final labels

- Local w6 0->4: SOMEWHAT OUTLIER-SENSITIVE
- Global 0->2: ROBUST

SENSITIVITY ONLY — FORMAL V2 RESULTS UNCHANGED
