import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseCurrentAuditSession, SESSION_V1_UNSUPPORTED, validateAuditSessionV2 } from '../.tmp/audit-session-v2-validator/src/data/auditSessionV2.js';
import { formalAvailabilityLabel } from '../.tmp/audit-session-v2-validator/src/components/evidence/evidencePresentationLogic.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = relative => JSON.parse(fs.readFileSync(path.join(ROOT, relative), 'utf8'));
const source = relative => fs.readFileSync(path.join(ROOT, relative), 'utf8');
const dgra = read('public/data/evidence/dgraformer_etth1_session_v2.json');
const msgnet = read('public/data/evidence/msgnet_etth1_session_v2.json');

const formalBundle = (status, supported) => ({ evidence: { primary_inference: { status }, multiplicity: { supported } } });
const completeSupported = formalBundle('complete', true);
const completeNotSupported = formalBundle('complete', false);
const unavailableFormal = formalBundle('unavailable', null);
assert.equal(formalAvailabilityLabel(completeSupported, completeNotSupported), 'Formal inference · 2 / 2 displayed scopes available');
assert.equal(formalAvailabilityLabel(completeSupported, unavailableFormal), 'Formal inference · 1 / 2 displayed scopes available');
assert.equal(formalAvailabilityLabel(unavailableFormal, unavailableFormal), 'Formal inference unavailable');
assert.equal(formalAvailabilityLabel(null, null), 'Not audited');
assert.equal(formalAvailabilityLabel(completeSupported, completeNotSupported, true), 'Formal inference available');

assert.equal(validateAuditSessionV2(dgra).ok, true);
assert.equal(validateAuditSessionV2(msgnet).ok, true);
const rejectedV1 = parseCurrentAuditSession(JSON.stringify({ schema_version: '1.0' }));
assert.equal(rejectedV1.ok, false);
assert.deepEqual(rejectedV1.errors, [SESSION_V1_UNSUPPORTED]);

const dgraRelations = new Map();
for (const candidate of dgra.candidate_relations) {
  const key = `${candidate.source}->${candidate.target}`;
  const windows = dgraRelations.get(key) ?? new Set();
  candidate.retained_contexts.forEach(value => windows.add(value));
  dgraRelations.set(key, windows);
}
assert.equal(dgraRelations.size, 4);
assert.equal([...dgraRelations.values()].filter(windows => windows.size === 1).length, 2);
assert.equal([...dgraRelations.values()].filter(windows => windows.size > 1).length, 2);
const localFixture = dgra.cross_sample_evidence.find(item => item.candidate_id === 'dgra:window:6:0->4');
const allFixture = dgra.cross_sample_evidence.find(item => item.candidate_id === 'dgra:all:0->2');
assert.equal(localFixture.primary_inference.raw_p, 0.0010998900109989002);
assert.equal(localFixture.multiplicity.adjusted_q, 0.008799120087991202);
assert.equal(allFixture.primary_inference.raw_p, 0.00009999000099990002);
assert.equal(allFixture.multiplicity.adjusted_q, 0.00039996000399960006);
const localFamilyFixture = dgra.hypothesis_families.find(item => item.family_id === localFixture.family_id);
const globalFamilyFixture = dgra.hypothesis_families.find(item => item.family_id === allFixture.family_id);
assert.equal(localFamilyFixture.family_id, 'dgraformer.local.frozen40');
assert.equal(localFamilyFixture.size, 8);
assert.equal(globalFamilyFixture.family_id, 'dgraformer.all_retained.frozen40');
assert.equal(globalFamilyFixture.size, 4);
assert.notEqual(localFamilyFixture.family_id, globalFamilyFixture.family_id, 'local and global provenance must remain distinct');
const inactive = dgra.case_evidence.find(item => item.status === 'inactive');
assert.ok(inactive);
assert.equal(inactive.D, null);
assert.equal(inactive.focal_response, null);

assert.deepEqual(Object.fromEntries(msgnet.hypothesis_families.map(item => [item.scope, item.size])), { single_scale: 126, all_scales: 42 });
assert.ok(msgnet.case_evidence.every(item => item.controls.unique_count === 41));
assert.ok(msgnet.cross_sample_evidence.every(item => item.primary_inference.settings.sign_configurations === 16384));
const supported = Object.fromEntries(msgnet.hypothesis_families.map(family => [family.scope, msgnet.cross_sample_evidence.filter(item => item.family_id === family.family_id && item.multiplicity.supported === true).length]));
assert.deepEqual(supported, { single_scale: 27, all_scales: 14 });
const tests = msgnet.samples.map(item => item.sample_index);
assert.equal(tests.length, 14);
const single = msgnet.candidate_relations.find(item => item.candidate_id === 'single_scale:2:6->4');
const all = msgnet.candidate_relations.find(item => item.candidate_id === 'all_scales:6->4');
assert.ok(single && all);
for (const testId of tests) {
  const singleCase = msgnet.case_evidence.find(item => item.candidate_id === single.candidate_id && item.sample_id === testId);
  const allCase = msgnet.case_evidence.find(item => item.candidate_id === all.candidate_id && item.sample_id === testId);
  const sample = msgnet.samples.find(item => item.sample_index === testId);
  assert.ok(singleCase && allCase && sample);
  assert.equal(singleCase.baseline_reference.sample_id, sample.sample_id);
  assert.equal(allCase.baseline_reference.sample_id, sample.sample_id);
  assert.deepEqual(singleCase.intervention_output_reference.value.shape, sample.baseline_prediction.shape);
  assert.deepEqual(allCase.intervention_output_reference.value.shape, sample.baseline_prediction.shape);
}

// Presentation rows must be a lossless view of frozen planned_samples and exact candidate cases.
function exactBundle(session, predicate) {
  const candidate = session.candidate_relations.find(predicate);
  if (!candidate) return null;
  const evidence = session.cross_sample_evidence.find(item => item.cross_sample_evidence_id === candidate.cross_sample_evidence_id && item.candidate_id === candidate.candidate_id && item.family_id === candidate.family_id);
  const family = session.hypothesis_families.find(item => item.family_id === candidate.family_id && item.members.includes(candidate.candidate_id));
  return evidence && family ? { candidate, evidence, family } : null;
}
function exactCaseFor(session, candidate, testId) {
  const ids = candidate.case_evidence_ids.filter(id => session.case_evidence.some(item => item.case_evidence_id === id && item.candidate_id === candidate.candidate_id && item.sample_id === testId));
  assert.ok(ids.length <= 1, `${candidate.candidate_id} has duplicate exact cases for ${testId}`);
  return ids.length ? session.case_evidence.find(item => item.case_evidence_id === ids[0]) : null;
}
for (const session of [dgra, msgnet]) {
  for (const candidate of session.candidate_relations) {
    const bundle = exactBundle(session, item => item.candidate_id === candidate.candidate_id);
    assert.ok(bundle, `${candidate.candidate_id} must resolve to exact frozen evidence and family`);
    const rows = bundle.evidence.planned_samples.map(testId => ({ testId, record: exactCaseFor(session, candidate, testId) }));
    assert.equal(rows.length, bundle.evidence.planned_samples.length);
    assert.deepEqual(rows.map(row => row.testId), bundle.evidence.planned_samples, 'table order must remain frozen protocol order');
    for (const row of rows) {
      if (!row.record) continue;
      assert.equal(row.record.candidate_id, candidate.candidate_id);
      assert.equal(row.record.sample_id, row.testId);
      if (row.record.status === 'inactive') {
        assert.equal(row.record.D, null);
        assert.equal(row.record.focal_response, null);
      }
    }
  }
}

const missingCaseSession = structuredClone(dgra);
const missingCandidate = missingCaseSession.candidate_relations[0];
const missingEvidence = missingCaseSession.cross_sample_evidence.find(item => item.candidate_id === missingCandidate.candidate_id);
const missingTestId = missingEvidence.planned_samples[0];
missingCaseSession.case_evidence = missingCaseSession.case_evidence.filter(item => !(item.candidate_id === missingCandidate.candidate_id && item.sample_id === missingTestId));
const missingRows = missingEvidence.planned_samples.map(testId => ({ testId, record: exactCaseFor(missingCaseSession, missingCandidate, testId) }));
assert.equal(missingRows.length, missingEvidence.planned_samples.length, 'a missing exact case must not remove its planned row');
assert.equal(missingRows.find(row => row.testId === missingTestId).record, null, 'a missing exact case must remain unavailable without fallback');

for (const [relation, windows] of dgraRelations) {
  const [source, target] = relation.split('->').map(Number);
  const locals = [...windows].map(window => exactBundle(dgra, candidate => candidate.source === source && candidate.target === target && candidate.scope === 'single_window' && candidate.window_index === window));
  assert.ok(locals.every(Boolean), `${relation} must resolve every retained window by exact identity`);
  assert.ok(exactBundle(dgra, candidate => candidate.source === source && candidate.target === target && candidate.scope === 'all_retained_windows'), `${relation} must resolve its exact all-window candidate`);
}
for (let sourceIndex = 0; sourceIndex < 7; sourceIndex += 1) for (let targetIndex = 0; targetIndex < 7; targetIndex += 1) {
  if (sourceIndex === targetIndex) continue;
  for (const scaleIndex of [0, 1, 2]) assert.ok(exactBundle(msgnet, candidate => candidate.source === sourceIndex && candidate.target === targetIndex && candidate.scope === 'single_scale' && candidate.scale_index === scaleIndex));
  assert.ok(exactBundle(msgnet, candidate => candidate.source === sourceIndex && candidate.target === targetIndex && candidate.scope === 'all_scales'));
}

function expectInvalid(mutate, restore, fragment) {
  mutate();
  const result = validateAuditSessionV2(dgra);
  restore();
  assert.equal(result.ok, false);
  assert.ok(result.errors.some(error => error.includes(fragment)), `${fragment}: ${result.errors.join('; ')}`);
}
const cross = dgra.cross_sample_evidence[0];
const originalQ = cross.multiplicity.adjusted_q;
expectInvalid(() => { cross.multiplicity.adjusted_q = 1.2; }, () => { cross.multiplicity.adjusted_q = originalQ; }, 'adjusted_q is invalid');
const originalFamily = cross.family_id;
expectInvalid(() => { cross.family_id = 'wrong'; }, () => { cross.family_id = originalFamily; }, 'family/candidate reference mismatch');
const graphs = dgra.samples[0].contexts[0].graphs;
const savedGraphs = { ...graphs };
expectInvalid(() => { for (const key of Object.keys(graphs)) delete graphs[key]; }, () => { Object.assign(graphs, savedGraphs); }, 'missing graph tensors');
const graph = Object.values(graphs)[0];
const originalValue = graph.values[0][0];
expectInvalid(() => { graph.values[0][0] = Infinity; }, () => { graph.values[0][0] = originalValue; }, 'nonfinite');
const active = dgra.case_evidence.find(item => item.status === 'active' && item.intervention_output_reference?.value);
const originalShape = active.intervention_output_reference.value.shape;
expectInvalid(() => { active.intervention_output_reference.value.shape = [1, 1]; }, () => { active.intervention_output_reference.value.shape = originalShape; }, 'trajectory shape mismatch');
expectInvalid(() => { active.empirical_p = 0.1; }, () => { delete active.empirical_p; }, 'forbidden empirical_p');
expectInvalid(() => { active.response_metrics.empirical_p = 0.1; }, () => { delete active.response_metrics.empirical_p; }, 'response_metrics contains forbidden empirical_p');
const originalContext = active.context.window_index;
expectInvalid(() => { active.context.window_index = 999; }, () => { active.context.window_index = originalContext; }, 'trajectory/context mismatch');

const originalMode = dgra.audit_plan.audit_mode;
dgra.audit_plan.audit_mode = 'quick_inspection';
assert.equal(validateAuditSessionV2(dgra).ok, true, 'Quick Inspection Session v2 must remain importable');
dgra.audit_plan.audit_mode = originalMode;
const savedInference = cross.primary_inference;
const savedMultiplicity = cross.multiplicity;
cross.primary_inference = { ...savedInference, status: 'unavailable', method: null, raw_p: null, reason: 'Explicit fixture reason' };
cross.multiplicity = { ...savedMultiplicity, adjusted_q: null, supported: null, reason: 'Primary inference unavailable' };
assert.equal(validateAuditSessionV2(dgra).ok, true, 'explicit unavailable formal inference must remain importable');
cross.primary_inference = savedInference;
cross.multiplicity = savedMultiplicity;

const ui = source('src/components/SessionV2Evidence.tsx');
const evidenceUi = source('src/components/evidence/EvidencePresentation.tsx');
const completeUi = `${ui}\n${evidenceUi}`;
assert.match(ui, /Evidence Summary/);
assert.match(ui, /Single-window Detail/);
assert.match(ui, /All-window Detail/);
assert.match(ui, /Single-scale Detail/);
assert.match(ui, /All-scale Detail/);
assert.match(completeUi, /Scope Evidence Map/);
assert.match(completeUi, /Selected Scope Comparison/);
assert.match(completeUi, /All Test Results/);
assert.match(completeUi, /Selected Test Detail/);
assert.doesNotMatch(completeUi, /Descriptive same-test trajectory|Illustrative Case/);
assert.match(completeUi, /font-sans tabular-nums text-ink-700/);
assert.match(completeUi, /Frozen inference settings and sensitivity results, shown separately for each displayed scope/);
assert.doesNotMatch(completeUi, /const primary = local \?\? global/);
assert.match(completeUi, /Shared audit provenance/);
assert.match(completeUi, /Hypothesis families/);
assert.match(completeUi, /Exact candidate not audited/);
assert.match(completeUi, /local=\{local\} global=\{all\}/);
assert.match(completeUi, /local=\{single\} global=\{all\}/);
assert.doesNotMatch(completeUi, /<ProvenancePanel[^>]*bundle=\{/);
assert.match(completeUi, /Frozen candidate-level evidence status across displayed scopes/);
assert.match(completeUi, /planned_samples\.map\(testId => \(\{ testId, record: exactCase/);
assert.match(completeUi, /No zero value or alternate case was substituted/);
assert.doesNotMatch(completeUi, /const\s+supported\s*=\s*q\s*</);
assert.doesNotMatch(completeUi, /multiplicity\.supported\s*\|\|/);
assert.doesNotMatch(completeUi, /computeBH|calculatePValue|deriveSupported|aggregateCasesToFormalEvidence|inferRelationPattern/);
assert.doesNotMatch(completeUi, /Localized evidence|Distributed evidence|Stable dependency|Global importance|Robust evidence/);
const production = ['src/App.tsx','src/components/SessionV2Evidence.tsx','src/components/evidence/EvidencePresentation.tsx','src/components/MsgnetWorkspace.tsx','src/components/ImportedSessionV2Workspace.tsx','src/data/auditSessionV2View.ts'];
const legacy = /empirical_p|bh_adjusted_p|local_bh_supported_count|broader_context_bh_supported_count|global_bh_supported_count|bootstrap_repetitions|statistically significant|case significance/;
for (const file of production) assert.doesNotMatch(source(file), legacy, `${file} contains legacy production evidence usage`);

console.log('Session v2 web regression: PASS');
