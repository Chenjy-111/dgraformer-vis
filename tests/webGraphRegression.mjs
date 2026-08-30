import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { captureWebGraphBaseline } from '../scripts/freeze_web_graph_baseline.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const expected = JSON.parse(fs.readFileSync(path.join(ROOT, 'tests/fixtures/web_graph_baseline_v2.json'), 'utf8'));
const actual = captureWebGraphBaseline();

assert.deepEqual(actual, expected, 'browser graph data changed after Web Migration v2');
console.log('Web graph regression: DGraFormer, MSGNet, and MTGNN PASS');
