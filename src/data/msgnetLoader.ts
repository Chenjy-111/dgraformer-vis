export interface MsgnetContext {
  scale_index: number;
  period: number;
  fft_strength: number;
  scale_contribution: number;
  adaptive: number[][];
  effective: number[][];
}

export interface MsgnetEdgeImpact {
  scale_index: number;
  source: number;
  target: number;
  source_name: string;
  target_name: string;
  adaptive_weight: number;
  prediction_delta_abs: number;
  error_delta_mae: number;
  statistics: {
    control_mean_prediction_delta_abs: number;
    control_percentile: number;
    empirical_p: number;
    bh_adjusted_p: number;
  };
}

export interface MsgnetSample {
  sample_index: number;
  history: number[][];
  ground_truth: number[][];
  prediction: number[][];
  metrics: { mse: number; mae: number };
  contexts: MsgnetContext[];
  edge_impacts: MsgnetEdgeImpact[];
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
  edge_impacts: Record<string, MsgnetEdgeImpact>;
}

export interface MsgnetCatalog {
  model: 'MSGNet';
  dataset: 'ETTh1';
  variables: string[];
  lookback: number;
  horizon: number;
  checkpoint_sha256: string;
  case_count: number;
  samples: Record<string, MsgnetSample>;
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
  const edge_impacts = Object.fromEntries(
    sample.edge_impacts.map((impact) => [
      `${impact.scale_index}:${impact.source}:${impact.target}`,
      impact,
    ])
  );
  const index = { variables, edge_impacts };
  evidenceCache.set(sample, index);
  return index;
}

export function loadMsgnetCatalog(): Promise<MsgnetCatalog> {
  if (!catalogPromise) {
    const base = import.meta.env.BASE_URL ?? '/';
    catalogPromise = fetch(`${base}data/models/msgnet/etth1/catalog.json`).then(async (response) => {
      if (!response.ok) throw new Error(`MSGNet data could not be loaded (${response.status}).`);
      return response.json() as Promise<MsgnetCatalog>;
    });
  }
  return catalogPromise;
}
