import type { AttentionScale, SampleData, ScaleId } from '@/types/demo';

export function getScale(sample: SampleData, scale: ScaleId): AttentionScale {
  return scale === 1 ? sample.attention.scale_1 : scale === 2 ? sample.attention.scale_2 : sample.attention.scale_3;
}

export function headMatrix(s: AttentionScale, head: number): number[][] {
  return head < 0 ? s.mean : s.heads[head] ?? s.mean;
}

/** Time-step range covered by a patch index at a given scale. */
export function patchRange(s: AttentionScale, patchIdx: number): [number, number] {
  const start = patchIdx * s.patchSteps;
  return [start, start + s.patchSteps];
}

export function attentionConcentration(mat: number[][]): number {
  // mean diagonal mass: how much each query attends to its own/near patch
  const n = mat.length;
  let diag = 0;
  for (let i = 0; i < n; i++) diag += mat[i][i];
  return Math.round((diag / n) * 1000) / 1000;
}

export function strongestLink(mat: number[][]): { q: number; k: number; w: number } {
  let best = { q: 0, k: 0, w: -1 };
  for (let q = 0; q < mat.length; q++) {
    for (let k = 0; k < mat[q].length; k++) {
      if (mat[q][k] > best.w) best = { q, k, w: mat[q][k] };
    }
  }
  best.w = Math.round(best.w * 1000) / 1000;
  return best;
}
