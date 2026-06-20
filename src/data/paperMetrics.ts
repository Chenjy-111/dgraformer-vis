import type { BaselineId, DatasetId, Horizon } from '@/types/demo';

// Real numbers transcribed from DGraFormer Table 1 (IJCAI-25), per dataset.
// Each entry is ordered by horizon [96, 192, 336, 720], values [mse, mae].
type Quad = [[number, number], [number, number], [number, number], [number, number]];

export const HORIZONS: Horizon[] = [96, 192, 336, 720];

export const OURS: Record<DatasetId, Quad> = {
  ETTh1: [[0.367, 0.393], [0.438, 0.426], [0.479, 0.442], [0.484, 0.467]],
  ETTh2: [[0.300, 0.344], [0.382, 0.397], [0.388, 0.415], [0.418, 0.436]],
  ETTm1: [[0.326, 0.366], [0.358, 0.376], [0.387, 0.397], [0.446, 0.436]],
  ETTm2: [[0.173, 0.253], [0.243, 0.302], [0.315, 0.348], [0.404, 0.401]],
  Weather: [[0.168, 0.207], [0.213, 0.249], [0.270, 0.291], [0.345, 0.338]],
  Electricity: [[0.136, 0.229], [0.155, 0.244], [0.171, 0.261], [0.210, 0.298]],
  Solar: [[0.184, 0.219], [0.211, 0.234], [0.234, 0.250], [0.235, 0.254]],
  Traffic: [[0.442, 0.245], [0.469, 0.257], [0.481, 0.266], [0.510, 0.281]],
  Flight: [[0.143, 0.250], [0.143, 0.247], [0.154, 0.257], [0.191, 0.291]],
  AirQualityUCI: [[1.147, 0.580], [1.238, 0.606], [1.344, 0.644], [1.482, 0.696]],
};

const ITRANSFORMER: Record<DatasetId, Quad> = {
  ETTh1: [[0.386, 0.405], [0.441, 0.436], [0.487, 0.458], [0.503, 0.491]],
  ETTh2: [[0.297, 0.349], [0.380, 0.400], [0.428, 0.432], [0.427, 0.445]],
  ETTm1: [[0.334, 0.368], [0.377, 0.391], [0.426, 0.420], [0.491, 0.459]],
  ETTm2: [[0.180, 0.264], [0.250, 0.309], [0.311, 0.348], [0.412, 0.407]],
  Weather: [[0.174, 0.214], [0.221, 0.254], [0.278, 0.296], [0.358, 0.349]],
  Electricity: [[0.148, 0.240], [0.162, 0.253], [0.178, 0.269], [0.225, 0.317]],
  Solar: [[0.203, 0.237], [0.233, 0.261], [0.248, 0.273], [0.249, 0.275]],
  Traffic: [[0.395, 0.268], [0.417, 0.276], [0.433, 0.283], [0.467, 0.302]],
  Flight: [[0.144, 0.252], [0.147, 0.253], [0.159, 0.266], [0.193, 0.297]],
  AirQualityUCI: [[1.192, 0.601], [1.308, 0.633], [1.401, 0.659], [1.532, 0.708]],
};

const MSGNET: Record<DatasetId, Quad> = {
  ETTh1: [[0.390, 0.411], [0.442, 0.442], [0.480, 0.468], [0.494, 0.488]],
  ETTh2: [[0.328, 0.371], [0.402, 0.414], [0.435, 0.443], [0.417, 0.441]],
  ETTm1: [[0.319, 0.366], [0.376, 0.397], [0.417, 0.422], [0.481, 0.458]],
  ETTm2: [[0.177, 0.262], [0.247, 0.307], [0.312, 0.346], [0.414, 0.403]],
  Weather: [[0.163, 0.212], [0.212, 0.254], [0.272, 0.299], [0.350, 0.348]],
  Electricity: [[0.165, 0.274], [0.184, 0.292], [0.195, 0.302], [0.231, 0.332]],
  Solar: [[0.259, 0.285], [0.268, 0.293], [0.316, 0.326], [0.313, 0.326]],
  Traffic: [[0.598, 0.339], [0.616, 0.358], [0.651, 0.373], [0.699, 0.404]],
  Flight: [[0.183, 0.301], [0.189, 0.306], [0.206, 0.320], [0.253, 0.358]],
  AirQualityUCI: [[1.232, 0.616], [1.350, 0.658], [1.490, 0.675], [1.592, 0.717]],
};

// Synthetic multipliers for the remaining baselines (illustrative, > ours).
const SYNTH_FACTORS: Record<Exclude<BaselineId, 'iTransformer' | 'MSGNet'>, number> = {
  PatchTST: 1.09,
  TimesNet: 1.12,
  DLinear: 1.28,
  Crossformer: 1.22,
};

export function baselineMetric(
  baseline: BaselineId,
  dataset: DatasetId,
  horizon: Horizon
): { mse: number; mae: number } {
  const hi = HORIZONS.indexOf(horizon);
  if (baseline === 'iTransformer') {
    const [mse, mae] = ITRANSFORMER[dataset][hi];
    return { mse, mae };
  }
  if (baseline === 'MSGNet') {
    const [mse, mae] = MSGNET[dataset][hi];
    return { mse, mae };
  }
  const f = SYNTH_FACTORS[baseline];
  const [mse, mae] = OURS[dataset][hi];
  return { mse: round3(mse * f), mae: round3(mae * (1 + (f - 1) * 0.7)) };
}

export function oursMetric(dataset: DatasetId, horizon: Horizon) {
  const hi = HORIZONS.indexOf(horizon);
  const [mse, mae] = OURS[dataset][hi];
  return { mse, mae };
}

function round3(x: number) {
  return Math.round(x * 1000) / 1000;
}
