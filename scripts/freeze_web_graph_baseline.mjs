import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DEFAULT_OUTPUT = path.join(ROOT, 'tests', 'fixtures', 'web_graph_baseline_v2.json');

const read = relative => JSON.parse(fs.readFileSync(path.join(ROOT, relative), 'utf8'));
const sha256 = value => crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');

export function captureWebGraphBaseline() {
  const index = read('public/data/index.json');
  const dgraformer = index.samples.flatMap(entry => entry.horizons.flatMap(horizon => entry.sampleIds.map(sampleId => {
    const relative = `public/data/samples/${entry.dataset}_${String(sampleId).padStart(3, '0')}_h${horizon}.json`;
    const sample = read(relative);
    return {
      dataset: sample.dataset,
      sample_id: sample.sample_id,
      variables: sample.variables,
      baseline_prediction_sha256: sha256(sample.prediction),
      contexts: sample.windows.map(window => ({
        context_id: window.window_id,
        node_count: sample.variables.length,
        edge_identities_sha256: sha256(window.edges.map(edge => [edge.source, edge.target])),
        retained_edges_sha256: sha256(window.kept_edges),
        edge_records_sha256: sha256(window.edges),
        dynamic_graph_sha256: sha256(window.dynamic_graph),
        static_graph_sha256: sha256(window.static_graph),
        sparse_graph_sha256: sha256(window.sparse_graph),
      })),
    };
  })));

  const msgnetCatalog = read('public/data/models/msgnet/etth1/graph_catalog_v2.json');
  const msgnet = msgnetCatalog.samples.map(sample => ({
    sample_id: sample.sample_index,
    node_count: msgnetCatalog.variables.length,
    baseline_prediction_sha256: sha256(sample.prediction),
    contexts: sample.contexts.map(context => ({
      context_id: context.scale_index,
      layer: context.layer,
      adaptive_sha256: sha256(context.adaptive),
      effective_sha256: sha256(context.effective),
      edge_identities_sha256: sha256(context.adaptive.flatMap((row, source) => row.map((weight, target) => source === target ? null : [source, target, weight]).filter(Boolean))),
    })),
  }));

  const pipeline = read('tests/fixtures/pipeline_v2_graph_baseline.json');
  const mtgnn = pipeline.models.MTGNN;
  return {
    fixture_version: 1,
    rule: 'Read-only browser graph baseline captured before Web Migration v2 evidence UI changes.',
    dgraformer,
    msgnet,
    mtgnn_sha256: sha256(mtgnn),
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const output = process.argv[2] ? path.resolve(process.argv[2]) : DEFAULT_OUTPUT;
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, `${JSON.stringify(captureWebGraphBaseline(), null, 2)}\n`, 'utf8');
  console.log(output);
}
