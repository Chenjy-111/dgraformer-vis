import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const validatorPath = path.join(root, 'artifacts/preflight/audit-session-validator/auditSession.js');
const sessionPaths = {
  dgraformer: path.join(root, 'artifacts/sessions/dgraformer_etth1/dgrainsight_session.json'),
  msgnet: path.join(root, 'artifacts/sessions/msgnet_etth1/dgrainsight_session.json'),
};

function ensureSession(adapter) {
  const output = sessionPaths[adapter];
  if (fs.existsSync(output)) return;
  const executable = process.platform === 'win32' ? 'python' : 'python3';
  const config = path.join(root, `configs/export_session_${adapter}_etth1.json`);
  const run = spawnSync(executable, ['-m', 'dgraudit.cli.export_audit_session', '--config', config], {
    cwd: root,
    encoding: 'utf8',
  });
  assert.equal(run.status, 0, `Unable to generate ${adapter} test session:\n${run.stderr}`);
}

ensureSession('dgraformer');
ensureSession('msgnet');
assert.ok(fs.existsSync(validatorPath), 'Compile the validator with tsconfig.audit-session-validator.json first.');

const { findExactEvidence, parseAuditSession, validateAuditSession } = await import(pathToFileURL(validatorPath).href);
const dgraformer = JSON.parse(fs.readFileSync(sessionPaths.dgraformer, 'utf8'));
const msgnet = JSON.parse(fs.readFileSync(sessionPaths.msgnet, 'utf8'));

assert.deepEqual(validateAuditSession(dgraformer), { valid: true, session: dgraformer, errors: [] });
assert.deepEqual(validateAuditSession(msgnet), { valid: true, session: msgnet, errors: [] });

const external = structuredClone(msgnet);
external.model.name = 'ExternalGraphNet';
external.model.adapter = 'ExternalGraphNetAdapter';
external.model.adapter_id = 'external_graph_net';
external.model.native_context_type = 'learned_context';
for (const sample of external.samples) for (const context of sample.contexts) context.type = 'learned_context';
for (const record of external.evidence_records) {
  record.selection.model = 'ExternalGraphNet';
  record.selection.context_type = record.selection.scope === 'local' ? 'learned_context' : 'learned_context_set';
}
assert.deepEqual(
  validateAuditSession(external),
  { valid: true, session: external, errors: [] },
  'A self-describing external adapter must not require a frontend model enum or redeployment.',
);

const originalVersion = msgnet.schema_version;
msgnet.schema_version = 'dgrainsight.audit_session.v999';
assert.equal(validateAuditSession(msgnet).valid, false, 'Unsupported schema versions must be rejected.');
msgnet.schema_version = originalVersion;

const originalSampleId = msgnet.evidence_records[0].selection.sample_id;
msgnet.evidence_records[0].selection.sample_id = 'test:999999';
const referenceFailure = validateAuditSession(msgnet);
assert.equal(referenceFailure.valid, false, 'Graph/evidence sample mismatch must be rejected.');
assert.ok(referenceFailure.errors.some(error => error.includes('sample_id')));
msgnet.evidence_records[0].selection.sample_id = originalSampleId;

const originalSource = msgnet.evidence_records[0].selection.source;
msgnet.evidence_records[0].selection.source = (originalSource + 1) % msgnet.dataset.variables.length;
const relationFailure = validateAuditSession(msgnet);
assert.equal(relationFailure.valid, false, 'Evidence relation identity mismatch must be rejected.');
assert.ok(relationFailure.errors.some(error => error.includes('.selection.source disagrees')));
msgnet.evidence_records[0].selection.source = originalSource;

const originalShape = msgnet.samples[0].baseline_prediction.shape;
msgnet.samples[0].baseline_prediction.shape = [1, 1];
const shapeFailure = validateAuditSession(msgnet);
assert.equal(shapeFailure.valid, false, 'Declared tensor shape corruption must be rejected.');
assert.ok(shapeFailure.errors.some(error => error.includes('declared shape')));
msgnet.samples[0].baseline_prediction.shape = originalShape;

const originalCrossRunValue = dgraformer.cross_run_evidence.value;
dgraformer.cross_run_evidence.value = {};
const missingValueFailure = validateAuditSession(dgraformer);
assert.equal(missingValueFailure.valid, false, 'Missing evidence with a non-null value must be rejected.');
assert.ok(missingValueFailure.errors.some(error => error.includes('requires value=null')));
dgraformer.cross_run_evidence.value = originalCrossRunValue;

const exact = msgnet.evidence_records[0].selection;
assert.equal(findExactEvidence(msgnet, {
  sample: exact.sample_index,
  contextType: exact.context_type,
  contextIndex: exact.context_index,
  source: exact.source,
  target: exact.target,
}, 'local')?.evidence_id, msgnet.evidence_records[0].evidence_id);
assert.equal(findExactEvidence(msgnet, {
  sample: exact.sample_index + 1,
  contextType: exact.context_type,
  contextIndex: exact.context_index,
  source: exact.source,
  target: exact.target,
}, 'local'), undefined, 'Exact lookup must never substitute a nearby sample.');

assert.equal(msgnet.evidence_summary.local_bh_supported_count, 0);
assert.equal(msgnet.evidence_summary.broader_context_bh_supported_count, 0);
assert.equal(dgraformer.cross_run_evidence.status, 'missing');
assert.equal(dgraformer.cross_run_evidence.value, null);
assert.equal(parseAuditSession('{not json').valid, false, 'Malformed JSON must be rejected.');

console.log('Audit Session browser validator: 12 checks passed.');
