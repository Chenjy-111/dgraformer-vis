import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = JSON.parse(fs.readFileSync(path.join(ROOT, 'public/data/evidence/dgraformer_etth1_session_v2.json'), 'utf8'));
source.session.session_id = `${source.session.session_id}:quick-web-fixture`;
source.audit_plan.audit_mode = 'quick_inspection';
for (const item of source.cross_sample_evidence) {
  item.primary_inference = { ...item.primary_inference, status: 'unavailable', method: null, raw_p: null, reason: 'Cross-sample formal inference was not evaluated for this Quick Inspection.' };
  item.multiplicity = { ...item.multiplicity, adjusted_q: null, supported: null, reason: 'Primary inference unavailable in Quick Inspection.' };
}
const output = path.join(ROOT, 'tmp', 'web_quick_inspection_session_v2.json');
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, `${JSON.stringify(source)}\n`, 'utf8');
console.log(output);
