// Core data + UI types for DGraFormer-Vis.

export type DatasetId =
  | 'ETTh1'
  | 'ETTh2'
  | 'ETTm1'
  | 'ETTm2'
  | 'Weather'
  | 'Electricity'
  | 'Solar'
  | 'Traffic'
  | 'Flight'
  | 'AirQualityUCI';

export type Horizon = 96 | 192 | 336 | 720;

export type BaselineId =
  | 'iTransformer'
  | 'MSGNet'
  | 'PatchTST'
  | 'TimesNet'
  | 'DLinear'
  | 'Crossformer';

export type ViewMode =
  | 'forecast'
  | 'graph'
  | 'topk'
  | 'attention'
  | 'error'
  | 'ablation'
  | 'sensitivity'
  | 'narrative';

export type GraphLayout = 'matrix' | 'sidebyside' | '3d-timeline';
export type GraphSource = 'static' | 'dynamic' | 'sparse' | 'difference';
export type ScaleId = 1 | 2 | 3;
export type ExplanationDepth = 'brief' | 'standard' | 'technical';
export interface DatasetMeta {
  id: DatasetId;
  variables: string[];
  pointsPerDay: number; // m for one day
  venue: string;
}

export interface GraphEdge {
  source: number; // variable index
  target: number;
  weight: number; // 0..1
  rank: number; // 1-based within window
  kept: boolean;
}

export interface WindowData {
  window_id: number;
  start: number; // time step (relative to history start)
  end: number;
  static_graph: number[][]; // N x N (prior C, same across windows)
  dynamic_graph: number[][]; // N x N (Ew)
  sparse_graph: number[][]; // N x N (Etilde_w)
  edges: GraphEdge[]; // flattened off-diagonal edges of dynamic graph
  kept_edges: GraphEdge[];
  filtered_edges: GraphEdge[];
  top_edges: GraphEdge[]; // top ranked overall
  sparsity_ratio: number; // fraction filtered
  mean_error: number; // mean abs error of points inside window
  explanation: string;
}

export interface AttentionScale {
  scale: ScaleId;
  patchSteps: number; // steps per patch at this scale
  nPatches: number;
  heads: number[][][]; // [head][query][key]
  mean: number[][]; // averaged over heads
  variableHeads?: number[][][][]; // [variable][head][query][key]
  semantic: string;
}

export interface SampleData {
  dataset: DatasetId;
  sample_id: number;
  horizon: Horizon;
  variables: string[];
  targetDefault: number;
  history: number[][]; // [variable][time]
  ground_truth: number[][]; // [variable][future step]
  prediction: number[][];
  error: number[][]; // abs error [variable][future step]
  windows: WindowData[];
  windowSize: number; // m
  patchLen: number;
  attention: {
    scale_1: AttentionScale;
    scale_2: AttentionScale;
    scale_3: AttentionScale;
  };
  metrics: { mse: number; mae: number };
  baseline_predictions?: Partial<Record<BaselineId, number[][]>>;
  baseline_metrics?: Partial<Record<BaselineId, { mse: number; mae: number }>>;
  narrative: string;
}

export interface SensitivityCurve {
  param: 'm' | 'Ke' | 'alpha';
  dataset: DatasetId;
  x: number[];
  mse: number[];
  mae: number[];
  best: number;
  note: string;
}

export interface DatasetIndexEntry {
  dataset: DatasetId;
  variables: string[];
  venue: string;
  pointsPerDay: number;
  samples: number[];
  horizons: Horizon[];
}
