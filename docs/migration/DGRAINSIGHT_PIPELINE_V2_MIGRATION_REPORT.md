# DGraInsight Offline Audit Pipeline v2 Migration Report

Date: 2026-08-31  
Final status: **PIPELINE V2 MIGRATION PASS**

Scope was limited to the Offline Audit Pipeline v2. No web layout, visual
component, model training, sample/test selection, candidate-family selection,
adapter contract, or V01–V09 model-validation change was made.

## A. Graph preservation

1. **DGraFormer graph regression: PASS.** The 40 v1 samples, 5 native window
   contexts per sample, node counts, graph shapes, complete context tensors,
   retained-edge identities/weights/ranks, and baseline predictions match the
   frozen canonical graph fixture exactly.
2. **MSGNet graph regression: PASS.** The existing 5-sample v1 graph core is
   preserved exactly through Quick Inspection conversion. The shared Test 0 in
   the frozen 14-test formal artifact also matches the existing v1 history,
   ground truth, baseline prediction, sample metrics, three scale contexts,
   adaptive/effective tensors, relation weights, and ranks exactly.
3. **MTGNN graph regression: PASS.** The fixture sample, global graph context,
   learned/transpose adjacency tensors, retained relation, weight/rank, and
   baseline prediction match exactly.
4. **Graph tensor changes: none.** `dgraudit/adapters.py` is unchanged. Native
   context semantics remain DGraFormer=window, MSGNet=layer+scale, and
   MTGNN=global_graph.
5. **Baseline prediction changes: none.** Canonical baseline hashes match the
   Phase A fixture; maximum absolute difference is 0 for the frozen comparisons.

The regression fixture is `tests/fixtures/pipeline_v2_graph_baseline.json`, and
the freeze utility is `scripts/freeze_pipeline_v2_graph_baseline.py`.

## B. Old inference removal

6. **`local_audit.py` no longer supplies formal v2 inference.** It remains only
   as the Session v1 compatibility implementation. v1 output is labeled
   `Legacy single-case / legacy inference session`; the default CLI path emits
   v2. A v1 session requires explicit `--session-version 1` or `--legacy-v1`.
7. **DGraFormer B=100 with-replacement is absent from v2.** The v2 control
   protocol is `all_unique_eligible`, requires `with_replacement=false`, stores
   unique identities and responses, and rejects duplicate identities.
8. **Old case-level BH does not enter v2 formal evidence.** Case evidence has
   `formal_inference.status=not_evaluated`, `raw_p=null`, and `BH_q=null`.
   Formal raw p and BH q exist only under candidate-level
   `cross_sample_evidence`.
9. **No production v2 fields named** `local_bh_supported_count` or
   `broader_context_bh_supported_count` exist. The semantic, JSON, and
   TypeScript validators reject old case p/BH fields in v2 formal records.

Real/descriptive output is retained: focal response, prediction deltas,
baseline/intervention errors, unique control mean/median/count/identities,
rank, percentile, graph effects, trajectories/references, and provenance.
Legacy non-finite descriptive metrics are exported as null with an explicit
missing reason, never NaN/Inf.

## C. Formal audit

10. **Quick Inspection and Formal Evidence Audit are separate.** Quick mode is
    single-case descriptive inspection and explicitly says it is not
    cross-sample statistical evidence. Formal mode uses frozen samples,
    candidates, dependence, inference, and multiplicity.
11. **Formal audits require multiple predeclared units.** A one-unit formal
    config is accepted only when every primary inference is explicitly
    `unavailable`; it cannot manufacture a p-value.
12. **Candidate families are frozen before intervention.** Config validation
    requires `selection_frozen=true`, unique candidate IDs, declared members,
    and an exact family-size match.
13. **Active/inactive policy is implemented.** Inactive/not-exposed positions
    have `focal_response=null` and `D=null`, appear in `inactive_samples`, and
    are excluded without zero imputation.
14. **Unique controls are implemented.** DGraFormer local uses every other real
    retained same-window directed non-self edge. DGraFormer all-retained reuses
    the already-frozen broader matched-control rule and fails with
    `BROADER CONTROL PROTOCOL MISSING` if it cannot be reconstructed. MSGNet
    uses all other 41 directed non-self relations in the same test/scope.
    MTGNN Quick Inspection uses all other real retained global-graph relations.

The wizard exposes an explicit formal confirmation summary (samples,
candidates, metric, controls, dependence, primary method, BH, alpha) before
running. It does not modify the frozen fields after intervention output exists.

## D. Dependence and inference

15. **Dependence Audit fields:** protocol ID, sample IDs, raw span, ordered
    start positions, minimum/median start gap, adjacent overlap count, all-pair
    overlap count, same-continuous-series flag, classification, derivation,
    selected engine, and reason.
16. **DGraFormer primary method:** one-sided, null-centered, non-circular moving
    block bootstrap on mean D, with +1 correction, 10,000 repetitions, seed
    20260830, and primary L=3 only for the frozen overlapping 40-position
    protocol. L=2/L=4 and the named non-overlap/trimmed/median/outlier checks are
    sensitivity results, not alternate primary tests.
17. **MSGNet primary method:** one-sided complete exact sign-flip enumeration on
    mean D for 14 frozen non-overlapping tests; 2^14=16,384 configurations, ties
    counted `>=`, and no Monte Carlo +1 correction. `scale_index` is the formal
    single-scale identity; FFT period is case metadata only.
18. **Unknown dependence:** primary inference is unavailable with null raw p and
    an explicit reason unless a declared external dependence protocol exists.
19. **No p-value-driven engine selection exists.** Selection is determined only
    from predeclared protocol plus dependence classification. DGraFormer is not
    routed to MSGNet's engine, MSGNet is not routed to DGraFormer's engine, and
    MTGNN receives neither without a validated formal protocol.

The engine registry is in `dgraudit/v2/inference.py`; adapters remain responsible
only for model loading, graph extraction, prediction, and graph override.

## E. Multiple testing

20. **BH families come from frozen config membership.** DGraFormer local and
    all-retained families are separate; MSGNet single-scale and all-scale
    families are separate. BH receives the valid primary raw-p vector for that
    complete declared family/missing policy. The membership and raw-p vectors
    are hashed in provenance.
21. **Browser/UI selection cannot change a family.** Family construction and BH
    occur offline before session export. The browser contract is read, validate,
    and display only.
22. **MSGNet 126/42 regression: PASS.** Family sizes are 126 and 42; every one of
    2,352 cases has 41 unique controls; supported counts reproduce as 27 and 14.
23. **DGraFormer frozen reproduction: PASS.** Active D vectors, primary raw p,
    and BH q reproduce the frozen artifacts. In particular:
    `window 6, 0->4`: p=0.0010998900109989002,
    q=0.008799120087991202; `all-retained 0->2`:
    p=0.00009999000099990002, q=0.00039996000399960006.

Primary multiple testing remains BH. BY is stored only as a named sensitivity
result and never silently replaces BH.

## F. Session v2

24. **Top-level schema:** `schema_version`, `session`, `model`, `dataset`,
    `checkpoint`, `audit_plan`, `samples`, `relations`, `case_evidence`,
    `candidate_relations`, `hypothesis_families`, `cross_sample_evidence`,
    `dependence_audit`, `validation`, `provenance`, and `limitations`.
25. **Graph core uses v1 semantics.** Samples and sample relations retain the v1
    graph/model representation; only obsolete v1 evidence-record links are not
    copied into v2 sample relations.
26. **`case_evidence` is independent** and descriptive.
27. **`cross_sample_evidence` is independent** and candidate-level.
28. **`hypothesis_families` is independent** and frozen/hash-traceable.
29. **`dependence_audit` is independent** and drives engine compatibility.
30. **Primary and sensitivity are explicit separate structures.** Every
    sensitivity result has a name, role, method, settings, value/p/q/CI as
    applicable, and an interpretation boundary.

Writes are atomic and reject non-finite JSON. Production MSGNet export embeds
all intervention trajectories by default; `--no-embedded-trajectories` exists
only as a diagnostic/validation option.

## G. Compatibility

31. **Session v1 remains readable and its regression tests pass.** The v1 reader,
    schema, validator, immutable-artifact exporter, and 12 browser-validator
    checks remain available.
32. **The new CLI defaults to Session v2.** `python -m dgraudit audit` detects a
    Config v2 formal audit, or converts a v1 single-case run into v2 Quick
    Inspection with legacy inferential fields excluded.
33. **v1 is explicitly legacy.** Its help text, session metadata, and docs label
    its empirical p/case BH as compatibility data rather than cross-sample
    evidence.

## H. Validation

34. **Python validator: PASS.** It checks finite/shape-correct graph tensors,
    references, unique IDs/controls, D arithmetic, active/inactive partition,
    family integrity, p/q/support consistency, complete engine settings,
    dependence compatibility, and adapter-specific identity/scope rules.
35. **JSON Schema: PASS.** Both Audit Config v2 and Session v2 schemas validate
    the frozen configs/sessions. A dependency-free, fail-closed validator covers
    the schema keywords used by the project when the third-party `jsonschema`
    package is unavailable offline.
36. **TypeScript validator: PASS.** Explicit v2 types and validation exist for
    CaseEvidence, CandidateRelation, CrossSampleEvidence, HypothesisFamily,
    DependenceAudit, PrimaryInference, SensitivityResult, EvidenceStatus, and
    MissingReason, while the v1 type remains available.
37. **Round-trip tests: PASS.** Config/audit/Session/Python parse/JSON Schema/
    TypeScript validation preserve graph, case, candidate, family, dependence,
    and provenance layers.
38. **Negative tests: PASS.** Covered one-sample formal unavailable, empty and
    duplicate controls, post-inference family mutation, inactive D=0, family
    size mismatch, unknown dependence, missing graph tensor, q>1, and old p in
    cross-sample evidence.
39. **Graph regression tests: PASS.** All three existing adapter cores match the
    Phase A fixture; the shared MSGNet frozen Test 0 also matches exactly.
40. **Statistical reproduction tests: PASS.** DGraFormer frozen candidates and
    MSGNet 126/42, 41-controls, 16,384-enumeration, and 27/14 expectations pass.

Verification executed:

- 72 Python tests: PASS.
- v1 TypeScript/browser validator: 12 checks PASS.
- v2 TypeScript compilation and runtime validation: PASS.
- Python semantic + JSON Schema validation of DGraFormer and MSGNet formal v2
  exports: PASS.
- Production Vite build: PASS (2,523 modules transformed).

## I. Final

41. **Mock/fallback inference:** none. Missing or incompatible formal inference
    is null/unavailable with a reason; there is no fake statistic, nearest-case
    substitution, or inactive-to-zero fallback.
42. **Edge-specific conclusion hardcode:** none. Frozen candidate identities and
    expected fixture values are data/config/test inputs; inference engines and
    evidence-status logic do not branch on a named edge or relation.
43. **Remaining failures/blockers:** none.

**PIPELINE V2 MIGRATION PASS**

Per the migration stop condition, Web Migration has not started and requires
separate user confirmation.
