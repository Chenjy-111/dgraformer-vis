# DGraInsight Cross-Sample Evidence Validation V2

| Window | Edge | Active | Positive | Mean D | Median D | Block p | BH q | L2 p | L4 p | Non-overlap |
|---:|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|:---|
| 6 | 0->4 (HUFL→LUFL) | 28/40 | 17/28 (60.7%) | +0.00096245 | +0.00018522 | 0.00109989 | 0.0087991201 | 0.00269973 | 0.00059994001 | 7/9; p=0.08984375 |
| 0 | 0->2 (HUFL→MUFL) | 28/40 | 14/28 (50.0%) | +0.00014543 | -0.00002310 | 0.10278972 | 0.41115888 | 0.13448655 | 0.071692831 | 4/10; p=0.828125 |
| 1 | 0->4 (HUFL→LUFL) | 28/40 | 9/28 (32.1%) | -0.00034336 | -0.00045813 | 0.99710029 | 1 | 0.99820018 | 0.99750025 | 3/9; p=0.91015625 |
| 1 | 0->3 (HUFL→MULL) | 28/40 | 2/28 (7.1%) | -0.00041367 | -0.00039578 | 1 | 1 | 1 | 1 | 1/9; p=0.99804688 |
| 4 | 5->4 (LULL→LUFL) | 28/40 | 8/28 (28.6%) | -0.00043084 | -0.00070890 | 0.91580842 | 1 | 0.93150685 | 0.90270973 | 3/10; p=0.9453125 |
| 1 | 5->4 (LULL→LUFL) | 28/40 | 6/28 (21.4%) | -0.00053298 | -0.00052999 | 1 | 1 | 1 | 1 | 1/9; p=0.99804688 |
| 2 | 5->4 (LULL→LUFL) | 29/40 | 1/29 (3.4%) | -0.00096027 | -0.00078128 | 1 | 1 | 1 | 1 | 1/10; p=0.99902344 |
| 0 | 0->4 (HUFL→LUFL) | 28/40 | 1/28 (3.6%) | -0.00147368 | -0.00150645 | 1 | 1 | 1 | 1 | 0/10; p=1 |

## Inference metadata

- Primary effect: mean D across all active observations in the 40 predeclared positions.
- Robust descriptive effect: median D.
- Primary test: one-sided null-centered moving-block bootstrap.
- B_bootstrap = 10000; seed = 20260830.
- Raw span = 192; minimum sample start gap = 71.
- Primary block length = ceil(192/71) = 3 samples.
- Sensitivity block lengths: L=2 and L=4.
- Blocks are non-circular consecutive sample-position blocks; inactive positions stay inactive after resampling and never contribute D=0.
- Conservative non-overlap sensitivity uses the fixed 14-sample subset: [0, 214, 428, 642, 857, 1071, 1285, 1499, 1713, 1927, 2142, 2356, 2570, 2784].
- All-sample exact sign tests are retained as DESCRIPTIVE / IID-NAIVE only.

## Structural Weight vs Cross-sample Evidence

- rho_weight_vs_median_D = 0.4047619; p = 0.31988864
- rho_weight_vs_positive_rate = 0.4047619; p = 0.31988864
- These are descriptive associations only.

## Global family

| Edge | Active | Positive | Mean D | Median D | Block p | BH q | L2 p | L4 p | Non-overlap |
|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|:---|
| 0->2 (HUFL→MUFL) | 28/40 | 22/28 (78.6%) | +0.00124600 | +0.00115861 | 9.9990001e-05 | 0.00039996 | 9.9990001e-05 | 9.9990001e-05 | 8/10; p=0.0546875 |
| 0->3 (HUFL→MULL) | 28/40 | 17/28 (60.7%) | +0.00007818 | +0.00014896 | 0.2889711 | 0.57794221 | 0.27177282 | 0.2249775 | 4/9; p=0.74609375 |
| 0->4 (HUFL→LUFL) | 40/40 | 13/40 (32.5%) | -0.00100473 | -0.00082254 | 1 | 1 | 1 | 1 | 3/14; p=0.99353027 |
| 5->4 (LULL→LUFL) | 40/40 | 8/40 (20.0%) | -0.00147825 | -0.00175726 | 1 | 1 | 1 | 1 | 3/14; p=0.99353027 |

## Required answers

- Q1: LOCAL raw block p < .05 = 1; BH q < .05 = 1.
- Q2: GLOBAL raw block p < .05 = 1; BH q < .05 = 1.
- Q3: global 0->2: mean D = +0.00124600; median D = +0.00115861; positive = 22/28; block p = 9.9990001e-05; BH q = 0.00039996; L2 p = 9.9990001e-05; L4 p = 9.9990001e-05; non-overlap p = 0.0546875; block-mean CI95 = [+0.00069482, +0.00173840].
- Q4: local w6 0->4: mean D = +0.00096245; median D = +0.00018522; positive = 17/28; block p = 0.00109989; BH q = 0.0087991201; L2 p = 0.00269973; L4 p = 0.00059994001; non-overlap p = 0.08984375; block-mean CI95 = [+0.00041921, +0.00159150].
- Q5: YES. no candidate crosses the raw p=.05 decision boundary.
- Q6: MIXED. Corrected-supported relations w6 0->4, 0->2 retain the same positive direction; opposite-direction sensitivity occurs for: w0 0->2 (mean D=+0.00014543; non-overlap=4/10); 0->3 (mean D=+0.00007818; non-overlap=4/9).
- Q7: classifications are listed below.

| Family | Relation | Classification |
|:---|:---|:---|
| Local | w0 0->2 | no consistent evidence |
| Local | w0 0->4 | no consistent evidence |
| Local | w1 0->3 | no consistent evidence |
| Local | w1 0->4 | no consistent evidence |
| Local | w1 5->4 | no consistent evidence |
| Local | w2 5->4 | no consistent evidence |
| Local | w4 5->4 | no consistent evidence |
| Local | w6 0->4 | cross-sample supported |
| Global | 0->2 | cross-sample supported |
| Global | 0->3 | directional but not corrected-supported |
| Global | 0->4 | no consistent evidence |
| Global | 5->4 | no consistent evidence |

RESULTS ONLY
