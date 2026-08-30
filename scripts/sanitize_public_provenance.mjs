import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const RUNS = {
  intervention: '59573278fc173879bbacef9ae99073f04faa7587dd4659ecad5b4eabe3684cb9',
  local: '3e83451437fe946a975b56fe6528fa2136443b9b08b966d3a9a78041849a6442',
};

function read(relative) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relative), 'utf8'));
}

function write(relative, value, compact = false) {
  fs.writeFileSync(path.join(ROOT, relative), `${JSON.stringify(value, null, compact ? 0 : 2)}\n`);
}

function sha256(relative) {
  return crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT, relative))).digest('hex');
}

function portablePath(value) {
  const normalized = value.replaceAll('\\', '/');
  if (!/^[A-Za-z]:\/Users\//i.test(normalized)) return value;
  const repoMarker = '/dgraformer-vis/';
  const repoIndex = normalized.toLowerCase().indexOf(repoMarker.toLowerCase());
  if (repoIndex >= 0) return normalized.slice(repoIndex + repoMarker.length);
  for (const [marker, token] of [
    ['/DGraFormer-main/DGraFormer-main/', '<DGRAFORMER_SOURCE>/'],
    ['/MSGNet-main/', '<MSGNET_SOURCE>/'],
    ['/iTransformer_datasets/', '<ETT_DATASET_ROOT>/'],
  ]) {
    const index = normalized.toLowerCase().indexOf(marker.toLowerCase());
    if (index >= 0) return `${token}${normalized.slice(index + marker.length)}`;
  }
  return `<EXTERNAL_RESOURCE>/${path.posix.basename(normalized)}`;
}

function transform(value, transformString) {
  if (typeof value === 'string') return transformString(value);
  if (Array.isArray(value)) return value.map(item => transform(item, transformString));
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, transform(item, transformString)]));
  }
  return value;
}

function sanitize(relative, compact = false) {
  write(relative, transform(read(relative), portablePath), compact);
}

function sanitizeLegacyJsonText(relative) {
  const absolute = path.join(ROOT, relative);
  let text = fs.readFileSync(absolute, 'utf8');
  const replacements = [
    ['C:\\\\Users\\\\cj\\\\Desktop\\\\files (1)\\\\dgraformer-vis\\\\', ''],
    ['C:\\\\Users\\\\cj\\\\Desktop\\\\DGraFormer-main\\\\DGraFormer-main\\\\', '<DGRAFORMER_SOURCE>/'],
    ['C:\\\\Users\\\\cj\\\\Desktop\\\\MSGNet-main\\\\', '<MSGNET_SOURCE>/'],
    ['C:\\\\Users\\\\cj\\\\Downloads\\\\iTransformer_datasets\\\\iTransformer_datasets\\\\', '<ETT_DATASET_ROOT>/'],
    ['C:\\\\Users\\\\cj\\\\', '<EXTERNAL_RESOURCE>/'],
  ];
  for (const [before, after] of replacements) text = text.replaceAll(before, after);
  fs.writeFileSync(absolute, text);
}

const localCatalog = `artifacts/runs/${RUNS.local}/evidence_catalog.json`;
const localManifest = `artifacts/runs/${RUNS.local}/manifest.json`;
const interventionManifest = `artifacts/runs/${RUNS.intervention}/manifest.json`;
const interventionPlan = `artifacts/runs/${RUNS.intervention}/plan.json`;

const oldLocalManifestSha = sha256(localManifest);
const oldInterventionManifestSha = sha256(interventionManifest);

sanitizeLegacyJsonText(localCatalog);
const localManifestValue = transform(read(localManifest), portablePath);
localManifestValue.evidence_catalog_sha256 = sha256(localCatalog);
write(localManifest, localManifestValue);
sanitize(interventionManifest);
sanitize(interventionPlan);

const replacements = new Map([
  [oldLocalManifestSha, sha256(localManifest)],
  [oldInterventionManifestSha, sha256(interventionManifest)],
]);

const relocatedLegacyPaths = new Map([
  ['../public/data/evidence/etth1_intervention_catalog.json', '../legacy/v1/artifacts/public-data/evidence/etth1_intervention_catalog.json'],
  ['../public/data/evidence/etth1_global_intervention_catalog.json', '../legacy/v1/artifacts/public-data/evidence/etth1_global_intervention_catalog.json'],
  ['../public/data/models/msgnet/etth1/catalog.json', '../legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json'],
  ['public/data/evidence/etth1_intervention_catalog.json', 'legacy/v1/artifacts/public-data/evidence/etth1_intervention_catalog.json'],
  ['public/data/evidence/etth1_global_intervention_catalog.json', 'legacy/v1/artifacts/public-data/evidence/etth1_global_intervention_catalog.json'],
  ['public/data/models/msgnet/etth1/catalog.json', 'legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json'],
]);

// The legacy v1 graph-core fixture is intentionally not rewritten here.
// Its validator hashes the exact JSON numeric representation; regenerate it
// through export_audit_session.py when its provenance inputs change.
for (const relative of [
  'public/data/evidence/dgraformer_etth1_session_v2.json',
]) {
  if (!fs.existsSync(path.join(ROOT, relative))) continue;
  const sanitized = transform(read(relative), value => replacements.get(value) ?? relocatedLegacyPaths.get(value) ?? portablePath(value));
  write(relative, sanitized, true);
}

for (const [before, after] of replacements) {
  console.log(`${before} -> ${after}`);
}
