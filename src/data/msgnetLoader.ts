export interface MsgnetContext {
  scale_index: number;
  period: number;
  fft_strength: number;
  scale_contribution: number;
  adaptive: number[][];
  effective: number[][];
}

export interface MsgnetSample {
  sample_index: number;
  history: number[][];
  ground_truth: number[][];
  prediction: number[][];
  metrics: { mse: number; mae: number };
  contexts: MsgnetContext[];
}

export interface MsgnetVariableEvidence {
  mse: number;
  mae: number;
  truth: number[];
  prediction: number[];
  absolute_error: number[];
}

export interface MsgnetEvidenceIndex {
  variables: Record<string, MsgnetVariableEvidence>;
}

export interface MsgnetCatalog {
  model: 'MSGNet';
  dataset: 'ETTh1';
  variables: string[];
  lookback: number;
  horizon: number;
  checkpoint_sha256: string;
  samples: MsgnetSample[];
  notice: string;
}

let catalogPromise: Promise<MsgnetCatalog> | null = null;
const evidenceCache = new WeakMap<MsgnetSample, MsgnetEvidenceIndex>();

export function getMsgnetEvidenceIndex(sample: MsgnetSample): MsgnetEvidenceIndex {
  const cached = evidenceCache.get(sample);
  if (cached) return cached;
  const variables: MsgnetEvidenceIndex['variables'] = {};
  sample.prediction.forEach((prediction, variable) => {
    const truth = sample.ground_truth[variable];
    const absolute_error = prediction.map((value, step) => Math.abs(value - truth[step]));
    const squared_error = prediction.map((value, step) => (value - truth[step]) ** 2);
    variables[String(variable)] = {
      mse: squared_error.reduce((sum, value) => sum + value, 0) / squared_error.length,
      mae: absolute_error.reduce((sum, value) => sum + value, 0) / absolute_error.length,
      truth,
      prediction,
      absolute_error,
    };
  });
  const index = { variables };
  evidenceCache.set(sample, index);
  return index;
}

export function loadMsgnetCatalog(): Promise<MsgnetCatalog> {
  if (!catalogPromise) {
    const base = import.meta.env.BASE_URL ?? '/';
    catalogPromise = fetch(`${base}data/models/msgnet/etth1/graph_catalog_v2.json?v=web-v2`, { cache: 'no-store' }).then(async (response) => {
      if (!response.ok) throw new Error(`MSGNet data could not be loaded (${response.status}).`);
      const catalog = await response.json() as MsgnetCatalog;
      if (!Array.isArray(catalog.samples) || catalog.samples.length !== 5) {
        throw new Error('MSGNet catalog has an incompatible sample structure.');
      }
      return catalog;
    });
  }
  return catalogPromise;
}
