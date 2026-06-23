import type { SampleData } from '@/types/demo';

export interface ErrorPeak {
  step: number;
  value: number;
  windowId: number | null; // windows are in the look-back; future steps map to last window context
}

export function meanErrorSeries(sample: SampleData, variable: number): number[] {
  return sample.error[variable] ?? [];
}

export function topErrorPeaks(sample: SampleData, variable: number, k = 5): ErrorPeak[] {
  const e = sample.error[variable] ?? [];
  const idx = e.map((v, i) => ({ v, i })).sort((a, b) => b.v - a.v).slice(0, k);
  return idx.map(({ v, i }) => ({ step: i, value: Math.round(v * 1000) / 1000, windowId: null }));
}

export function targetMetrics(sample: SampleData, variable: number): { mse: number; mae: number } {
  const e = sample.error[variable] ?? [];
  if (e.length === 0) return { mse: 0, mae: 0 };
  const mae = e.reduce((a, b) => a + b, 0) / e.length;
  const mse = e.reduce((a, b) => a + b * b, 0) / e.length;
  return { mse: Math.round(mse * 1e6) / 1e6, mae: Math.round(mae * 1e6) / 1e6 };
}

export function horizonErrorGrowth(sample: SampleData, variable: number): { early: number; late: number } {
  const e = sample.error[variable] ?? [];
  if (e.length === 0) return { early: 0, late: 0 };
  const half = Math.floor(e.length / 2);
  const early = e.slice(0, half).reduce((a, b) => a + b, 0) / Math.max(1, half);
  const late = e.slice(half).reduce((a, b) => a + b, 0) / Math.max(1, e.length - half);
  return { early: Math.round(early * 1000) / 1000, late: Math.round(late * 1000) / 1000 };
}

/**
 * Heuristic diagnostic clues for an error peak. These are NOT causal claims;
 * they correlate model-internal signals with the observed error.
 */
export function diagnose(sample: SampleData, variable: number, step: number): string[] {
  const clues: string[] = [];
  const e = sample.error[variable] ?? [];
  const peak = e[step] ?? 0;
  const mean = e.reduce((a, b) => a + b, 0) / Math.max(1, e.length);

  if (peak > mean * 1.6) clues.push('This step is a local error spike (well above the average error for this variable).');
  if (step > sample.horizon * 0.6) clues.push('It falls in the far part of the horizon, where uncertainty and error accumulation grow.');

  // unstable graph clue: high variance of kept edge count across windows
  const keptCounts = sample.windows.map((w) => w.kept_edges.length);
  const variance = stdev(keptCounts);
  if (variance > 2) clues.push('The dynamic graph changes substantially across windows here, which can make feature aggregation less stable.');

  // sparsity clue
  const avgSparsity = sample.windows.reduce((a, w) => a + w.sparsity_ratio, 0) / sample.windows.length;
  if (avgSparsity > 0.6) clues.push('Top-K focusing is aggressive (high sparsity); a useful but lower-ranked edge may have been filtered out.');

  // low attention concentration clue
  clues.push('Inspect multi-scale attention near this step: diffuse attention can signal weaker temporal evidence.');

  if (clues.length === 0) clues.push('No strong diagnostic signal; the error is close to the typical range for this variable.');
  return clues;
}

function stdev(xs: number[]): number {
  if (xs.length === 0) return 0;
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length);
}
