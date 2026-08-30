import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const read = relative => JSON.parse(fs.readFileSync(path.join(ROOT, relative), 'utf8'));
const write = (relative, value) => fs.writeFileSync(path.join(ROOT, relative), `${JSON.stringify(value)}\n`, 'utf8');

const dgraPath = 'public/data/evidence/dgraformer_etth1_session_v2.json';
const dgra = read(dgraPath);
const forbiddenCaseMetrics = new Set(['empirical_p', 'bh_adjusted_p', 'effect_difference_bootstrap_ci', 'weight_impact_spearman_p']);
for (const record of dgra.case_evidence) {
  for (const key of Object.keys(record.response_metrics ?? {})) if (forbiddenCaseMetrics.has(key)) delete record.response_metrics[key];
}
write(dgraPath, dgra);

const legacyCatalog = read('legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json');
const graphCatalog = {
  model: legacyCatalog.model,
  dataset: legacyCatalog.dataset,
  variables: legacyCatalog.variables,
  lookback: legacyCatalog.lookback,
  horizon: legacyCatalog.horizon,
  checkpoint_sha256: legacyCatalog.checkpoint_sha256,
  samples: legacyCatalog.samples.map(sample => ({
    sample_index: sample.sample_index,
    history: sample.history,
    ground_truth: sample.ground_truth,
    prediction: sample.prediction,
    metrics: sample.metrics,
    contexts: sample.contexts,
  })),
  notice: 'Read-only graph and baseline prediction artifact. Formal evidence is loaded from Session v2.',
};
write('public/data/models/msgnet/etth1/graph_catalog_v2.json', graphCatalog);

console.log(JSON.stringify({ dgra_case_records: dgra.case_evidence.length, msgnet_graph_samples: graphCatalog.samples.length }));
