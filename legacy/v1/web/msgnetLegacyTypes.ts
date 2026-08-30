// LEGACY SESSION V1 COMPATIBILITY ONLY. Not used by the current Session v2 formal inference path.
import type { MsgnetContext } from '../../../src/data/msgnetLoader';

// Compatibility-only types for retired pre-Session-v2 built-in evidence panels.
// No module reachable from App.tsx imports this file.
export interface MsgnetEdgeImpact {
  sample_index: number; scale_index: number; source: number; target: number;
  source_name: string; target_name: string; adaptive_weight: number;
  prediction_delta_abs: number; error_delta_mae: number;
  statistics: { control_mean_prediction_delta_abs: number; control_percentile: number; empirical_p: number; bh_adjusted_p: number };
}
export interface MsgnetGlobalEdgeImpact {
  sample_index: number; source: number; target: number; source_name: string; target_name: string;
  scope: 'all_scales'; affected_scales: number[]; scale_weights: number[];
  prediction_delta_abs: number; prediction_delta_max: number; error_delta_mae: number; error_delta_mse: number;
  intervention_prediction: number[][];
  statistics: MsgnetEdgeImpact['statistics'] & { control_median_prediction_delta_abs: number; standardized_effect_size: number; candidate_minus_control_mean_bootstrap_ci_95: [number, number]; bootstrap_repetitions: number };
}
export interface MsgnetLegacySample {
  sample_index: number; history: number[][]; ground_truth: number[][]; prediction: number[][];
  metrics: { mse: number; mae: number }; contexts: MsgnetContext[];
  edge_impacts: MsgnetEdgeImpact[]; global_edge_impacts: MsgnetGlobalEdgeImpact[];
}
export interface MsgnetLegacyCatalog {
  model: 'MSGNet'; dataset: 'ETTh1'; variables: string[]; lookback: number; horizon: number;
  checkpoint_sha256: string; case_count: number; global_case_count: number; global_bh_supported_count: number;
  global_intervention_run_id: string; samples: MsgnetLegacySample[]; notice: string;
}
