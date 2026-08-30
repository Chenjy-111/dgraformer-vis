import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseCurrentAuditSession, SESSION_V1_UNSUPPORTED, validateAuditSessionV2 } from '../.tmp/audit-session-v2-validator/src/data/auditSessionV2.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = relative => JSON.parse(fs.readFileSync(path.join(ROOT, relative), 'utf8'));
const source = relative => fs.readFileSync(path.join(ROOT, relative), 'utf8');
const dgra = read('public/data/evidence/dgraformer_etth1_session_v2.json');
const msgnet = read('public/data/evidence/msgnet_etth1_session_v2.json');

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
assert.match(ui, /Evidence Summary/);
assert.match(ui, /Single-window Detail/);
assert.match(ui, /All-window Detail/);
assert.match(ui, /Single-scale Detail/);
assert.match(ui, /All-scale Detail/);
assert.match(ui, /No zero value or alternate case was substituted/);
assert.doesNotMatch(ui, /const\s+supported\s*=\s*q\s*</);
const production = ['src/App.tsx','src/components/SessionV2Evidence.tsx','src/components/MsgnetWorkspace.tsx','src/components/ImportedSessionV2Workspace.tsx','src/data/auditSessionV2View.ts'];
const legacy = /empirical_p|bh_adjusted_p|local_bh_supported_count|broader_context_bh_supported_count|global_bh_supported_count|bootstrap_repetitions|statistically significant|case significance/;
for (const file of production) assert.doesNotMatch(source(file), legacy, `${file} contains legacy production evidence usage`);

console.log('Session v2 web regression: PASS');
