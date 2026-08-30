import fs from 'node:fs';
import { validateAuditSessionV2 } from '../.tmp/audit-session-v2-validator/src/data/auditSessionV2.js';

const path = process.argv[2];
if (!path) throw new Error('Usage: node tests/auditSessionV2Validator.mjs <session-v2.json>');
const result = validateAuditSessionV2(JSON.parse(fs.readFileSync(path, 'utf8')));
if (!result.ok) {
  console.error(result.errors.join('\n'));
  process.exit(1);
}
console.log('TYPESCRIPT SESSION V2 VALID');
