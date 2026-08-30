# DGraInsight Web Migration v2 Report

Date: 2026-08-31  
Scope: Web Migration only. Pipeline v2 inference, frozen protocols, adapters,
V01–V11, graph extraction/tensors, baseline predictions, and intervention
outputs were not changed.

## A. Graph preservation

1. **DGraFormer graph regression:** PASS.
2. **MSGNet graph regression:** PASS.
3. **MTGNN graph regression:** PASS.
4. **Graph tensor values changed:** No. The pre-migration browser fixture checks
   every DGraFormer sample/context graph hash, every MSGNet scale tensor hash,
   and the MTGNN frozen graph-core hash.
5. **Baseline predictions changed:** No. DGraFormer and MSGNet browser-source
   prediction hashes and the frozen MTGNN baseline remain identical.
6. **Dynamic graph first/main:** Yes. Existing DGraFormer graph controls and
   renderer remain first. MSGNet opens its existing dynamic scale graph first;
   formal evidence is below it and hidden until an edge click.

Baseline: `tests/fixtures/web_graph_baseline_v2.json`. Regression command:
`npm run test:web-graph-regression`.

## B. Legacy statistics

7. **Legacy single-case empirical p in production v2 UI:** No.
8. **Old case-level BH in production v2 UI:** No.
9. **Old B=100 statistics in formal v2 UI:** No.
10. **V1 compatibility isolated:** Yes. V1 remains importable, is labeled
    `Legacy Session v1`, retains graph/case browsing, and is never presented as
    candidate-level cross-sample evidence.
11. **Production-v2 legacy-field references:** **0** across the modules/assets
    reachable by the v2 UI. The complete audit classified 11 compatibility-only
    occurrences, 7,195 retired/historical fixture occurrences, and two validator
    rejection literals. Historical catalogs are not fetched by the v2 UI; the
    new MSGNet graph-only catalog and both formal v2 assets contain zero legacy
    inferential fields.

The Web asset exporter removes unused old DGraFormer case-inference metrics and
creates a graph-only MSGNet catalog. It preserves graph tensors, predictions,
descriptive case values, D, controls, and every candidate-level Session v2 p/q.

## C. Session v2

12. **Existing Pipeline v2 TypeScript schema used:** Yes; no second web schema.
13. **`case_evidence` descriptive only:** Yes. Case cards show response,
    controls, D, rank/percentile, error deltas, and trajectories; no case p/BH.
14. **`cross_sample_evidence` candidate-level:** Yes.
15. **`hypothesis_families` read offline:** Yes; family ID, frozen size, and
    canonical support are displayed without browser reconstruction.
16. **`dependence_audit` read/displayed:** Yes, under Method Details.
17. **Browser p/BH recomputation:** None. Raw p, adjusted q, family size, and
    `supported` are exact offline Session v2 values.

V2 import fails closed for invalid schema/reference/family, q outside [0,1],
legacy case p/BH, missing graph tensors, nonfinite tensor values, and
trajectory/context or shape mismatch. A rejected import preserves the active
page/session atomically.

## D. DGraFormer

18. **Graph unchanged:** Yes.
19. **Neutral selector below graph:** Yes, `Relations to inspect`.
20. **Conclusions hidden before selection:** Yes.
21. **Current formal relation options:** 4 (data-derived, frozen order).
22. **One/multi-window behavior metadata-driven:** Yes, from retained contexts.
23. **One-window tabs:** Exactly 2 (`Evidence Summary`, `Intervention Detail`).
24. **Multi-window tabs:** Exactly 3 parallel tabs.
25. **Local window default outcome-independent:** Yes; current valid graph
    window or first retained-context order, never p/D/weight ordering.
26. **Single-window detail keeps sample selection:** Yes, all 40 frozen units.
27. **All-window detail keeps sample selection:** Yes, all 40 frozen units.
28. **Sample-level p/BH absent:** Yes.
29. **Inactive samples honest:** Yes; `Not exposed in this sample`, null D and
    focal response, no zero or nearest-case substitution.
30. **Frozen p/q fixtures exact:** Yes. W6 0→4 displays
    p=0.0010998900109989002 and q=0.008799120087991202; all-retained 0→2
    displays p=0.00009999000099990002 and q=0.00039996000399960006.

## E. MSGNet

31. **Relation selection:** Direct graph-edge click.
32. **Separate MSGNet relation-chip list:** None.
33. **Preselection click instruction:** Visible.
34. **Formal scale identity:** `scale_index`.
35. **FFT period:** Case metadata only.
36. **Top-level tabs:** Exactly 3 parallel tabs.
37. **Summary:** Side-by-side Single-scale vs All-scale.
38. **Summary trajectory:** Ground truth, original, single, and all are exact
    records from one identical selected test; incomplete sets fail closed.
39. **Detail test selectors:** Two real frozen tests in both detail tabs.
40. **Defaults outcome-independent:** Earliest and latest frozen tests.
41. **Unique controls:** 41 for every frozen MSGNet case.
42. **Family sizes:** 126 Single-scale and 42 All-scale, read from Session v2.
43. **Supported counts:** 27 and 14, unchanged and regression-checked.

Changing the summary test changes only the illustrative chart. Browser QA
confirmed the formal card text/p/q remains byte-for-byte unchanged.

## F. Scientific language

44. **Causal language avoided:** Yes; all claims are model/checkpoint-internal.
45. **Not audited vs unsupported distinguished:** Yes.
46. **Case vs formal evidence distinguished:** Yes.
47. **Primary inference vs sensitivity distinguished:** Yes.
48. **BH support vs robustness/sensitivity distinguished:** Yes. The browser
    does not manufacture a robustness category.

## G. State and missing handling

49. **Model switch reset:** PASS in browser; relation/context/tab/detail state
    unmounts and no stale p/q remains.
50. **Relation/edge switch reset:** PASS; one-window selection collapses 3→2
    tabs, and MSGNet edge changes return to the new edge Summary.
51. **Missing values converted to zero:** No.
52. **Nearest-case substitution:** None; all lookups are exact candidate/case
    references.
53. **Quick Inspection:** PASS; graph/case inspection remains and a neutral
    `Cross-sample formal inference was not evaluated` notice is shown.
54. **Unavailable formal inference:** Explicit reason shown; no q placeholder,
    zero, or `not significant` label.

## H. Build and validation

55. **TypeScript compile:** PASS (`tsc -b`).
56. **Vite production build:** PASS (2,164 modules transformed).
57. **V1 import regression:** PASS (12 validator checks plus real browser import).
58. **V2 import regression:** PASS (formal, Quick Inspection, rejected import).
59. **Graph regression:** PASS for DGraFormer, MSGNet, and MTGNN.
60. **Statistical display regression:** PASS; canonical frozen p/q/family/support.
61. **Same-test trajectory test:** PASS for every frozen MSGNet test in the
    regression fixture and through browser interaction.
62. **Legacy production-field search:** PASS; production v2 count = 0.
63. **Browser console errors/warnings:** 0 after DGraFormer/MSGNet switching,
    edge/relation changes, imports, narrow layout, and Quick Inspection.
64. **Mock/random/fallback evidence:** None.
65. **Edge-specific conclusion hardcode:** None. Relation IDs occur only in
    tests/fixtures; production branching uses candidate metadata and scope.

Verification commands:

- `npm run test:web-session-v2` — PASS
- `npm run test:session-validator` — PASS (12 checks)
- `npm run test:web-graph-regression` — PASS
- `tsc -b` — PASS
- `vite build --config vite.config.ts` — PASS
- Real in-app browser interaction and 390 px responsive QA — PASS

## I. Final status

**WEB MIGRATION V2 PASS**
