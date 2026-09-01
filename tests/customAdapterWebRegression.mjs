import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { validateAuditSessionV2 } from '../.tmp/audit-session-v2-validator/src/data/auditSessionV2.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'dgrainsight-custom-web-'));
try {
  const run = (config, fileName) => {
    const output = path.join(temporary, fileName);
    const execution = spawnSync('python', [
      '-m', 'dgraudit', 'audit', '--config', config, '--output', output,
    ], { cwd: ROOT, encoding: 'utf8' });
    assert.equal(execution.status, 0, `${execution.stdout}\n${execution.stderr}`);
    const session = JSON.parse(fs.readFileSync(output, 'utf8'));
    const validation = validateAuditSessionV2(session);
    assert.equal(validation.ok, true, validation.ok ? '' : validation.errors.join('\n'));
    return session;
  };
  const tiny = run('configs/custom_adapter_fixture.json', 'tiny-session-v2.json');
  assert.equal(tiny.model.adapter_id, 'tiny_external_fixture');
  assert.equal(tiny.samples[0].contexts[0].type, 'global');
  assert.equal(tiny.case_evidence[0].controls.unique_count, 5);
  assert.equal(tiny.case_evidence[0].formal_inference.status, 'not_evaluated');

  const mtgnnAssets = [
    'third_party/MTGNN/net.py',
    'third_party/MTGNN/util.py',
    'third_party/MTGNN/data/exchange_rate.txt',
    'artifacts/mtgnn_exchange/mtgnn_exchange_h3_seed42_state_dict.pt',
  ];
  if (mtgnnAssets.every(item => fs.existsSync(path.join(ROOT, item)))) {
    const mtgnn = run('configs/custom_adapter_mtgnn_exchange.json', 'mtgnn-session-v2.json');
    assert.equal(mtgnn.model.adapter_id, 'mtgnn_external');
    assert.equal(mtgnn.model.adapter_class, 'ExternalMTGNNAdapter');
    assert.equal(mtgnn.samples[0].contexts[0].type, 'global_graph');
    assert.equal(mtgnn.candidate_relations.length, 1, 'Quick Inspection must expose its one audited relation');
    assert.equal(mtgnn.case_evidence.length, 1, 'Quick Inspection must expose its one stored case replay');
    assert.equal(mtgnn.candidate_relations[0].source, mtgnn.relations[0].source);
    assert.equal(mtgnn.candidate_relations[0].target, mtgnn.relations[0].target);
    assert.equal(mtgnn.case_evidence[0].intervention_output_reference.status, 'available');
    assert.equal(mtgnn.case_evidence[0].controls.unique_count, 27);
    assert.equal(mtgnn.case_evidence[0].controls.responses.length, 27, 'The imported control plot needs every stored response');
    assert.ok(Number.isFinite(mtgnn.case_evidence[0].focal_response));
    assert.ok(Number.isFinite(mtgnn.case_evidence[0].D));
    assert.ok(Math.abs(mtgnn.case_evidence[0].D - (mtgnn.case_evidence[0].focal_response - mtgnn.case_evidence[0].controls.mean)) < 1e-12);
    assert.equal(mtgnn.case_evidence[0].formal_inference.status, 'not_evaluated');
    console.log('Custom adapter Session v2 Web import regression: tiny fixture + real MTGNN presentation operands PASS');
  } else {
    console.log('Custom adapter Session v2 Web import regression: tiny fixture PASS; real MTGNN assets not bundled (SKIP)');
  }
} finally {
  fs.rmSync(temporary, { recursive: true, force: true });
}
