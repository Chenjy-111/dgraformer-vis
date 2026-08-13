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
