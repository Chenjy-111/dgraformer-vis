import type { SampleData } from '@/types/demo';
import type { Explanation, ExplanationDepth } from '@/types/explanation';
import { horizonErrorGrowth } from './errorDiagnosis';

export interface NarrativeReport {
  title: string;
  sections: { heading: string; body: string }[];
}

export function generateNarrative(
  sample: SampleData,
  windowIdx: number,
  target: number,
  depth: ExplanationDepth
): NarrativeReport {
  const v = sample.variables[target];
  const win = sample.windows[windowIdx];
  const growth = horizonErrorGrowth(sample, target);
  const brief = depth === 'brief';
  const tech = depth === 'technical';

  const sections: { heading: string; body: string }[] = [];

  sections.push({
    heading: '1. Selected case',
    body: `Dataset ${sample.dataset}, sample ${sample.sample_id}, horizon ${sample.horizon}, target variable ${v}. The ${96}-step look-back is partitioned into ${sample.windows.length} windows of size ${sample.windowSize}.`,
  });

  sections.push({
    heading: '2. Forecast summary',
    body: `Reported MSE ${sample.metrics.mse}, MAE ${sample.metrics.mae}. Error grows from ${growth.early} (early horizon) to ${growth.late} (late horizon), consistent with information decay over longer horizons.`,
  });

  sections.push({
    heading: '3. Dynamic graph explanation',
    body:
      `In window ${windowIdx + 1}, DGraFormer learns a window-specific correlation graph E_w = alpha*C + (1-alpha)*R_w, mixing a static seasonal prior C with a learnable dynamic graph R_w. ` +
      (tech ? `The prior C is built from cosine similarity of the seasonal (Fourier-filtered) signal, while R_w is a learnable parameter matrix refined during training. ` : '') +
      `${win.kept_edges.length} of ${win.edges.length} directed edges survive focusing.`,
  });

  if (!brief) {
    sections.push({
      heading: '4. Top-K focusing explanation',
      body: `A mask M_w keeps the top correlation weights (sparsity ${Math.round(win.sparsity_ratio * 100)}%). This removes weak or spurious edges so message passing concentrates on essential relationships. Strongest retained edge: ${sample.variables[win.kept_edges[0]?.source ?? 0]} -> ${sample.variables[win.kept_edges[0]?.target ?? 1]} (weight ${win.kept_edges[0]?.weight.toFixed(2) ?? '-'}).`,
    });

    sections.push({
      heading: '5. Multi-scale attention explanation',
      body: `Three temporal scales are read: scale 1 (${sample.attention.scale_1.patchSteps}-step patches, short-term fluctuation), scale 2 (${sample.attention.scale_2.patchSteps}-step, periodic), scale 3 (${sample.attention.scale_3.patchSteps}-step, long-range trend). Combining scales lets the model use both local and global temporal evidence.`,
    });

    sections.push({
      heading: '6. Error diagnosis',
      body: `Window ${windowIdx + 1} mean error is ${win.mean_error}. Larger errors tend to appear later in the horizon and in windows where the dynamic graph shifts most. These are diagnostic clues, not causal claims.`,
    });
  }

  sections.push({
    heading: tech ? '7. Evidence' : '4. Evidence',
    body: `Window span ${win.start}-${win.end}; kept edges ${win.kept_edges.length}; filtered edges ${win.filtered_edges.length}; sparsity ${Math.round(win.sparsity_ratio * 100)}%.`,
  });

  sections.push({
    heading: tech ? '8. Assumptions' : '5. Assumptions',
    body: `Edge weights are learned correlation strengths used for aggregation, not causal effects. Outputs are precomputed; the demo performs no inference.`,
  });

  sections.push({
    heading: tech ? '9. Caveats' : '6. Caveats',
    body: `Per-sample values are deterministic mocks calibrated to dataset-level paper metrics. Window sizing is chosen for visualization clarity.`,
  });

  sections.push({
    heading: tech ? '10. Takeaway' : '7. Takeaway',
    body: `DGraFormer adapts its inter-variable graph per window, focuses on essential correlations to suppress noise, and reads temporal structure at multiple scales \u2014 the combination explains its accuracy gains over static-graph and channel-independent baselines.`,
  });

  return { title: `Narrative report \u2014 ${sample.dataset} / ${v}`, sections };
}

export function reportToMarkdown(r: NarrativeReport): string {
  const lines = [`# ${r.title}`, ''];
  for (const s of r.sections) {
    lines.push(`## ${s.heading}`, '', s.body, '');
  }
  return lines.join('\n');
}

export function explanationToMarkdown(e: Explanation): string {
  const lines = [`# ${e.title}`, '', `*${e.selectionLabel}*`, '', e.summary, ''];
  if (e.evidence.length) {
    lines.push('## Evidence', '');
    for (const ev of e.evidence) lines.push(`- **${ev.label}:** ${ev.value}`);
    lines.push('');
  }
  if (e.formula) lines.push('## Formula', '', '```', e.formula, '```', '');
  if (e.assumption) lines.push('## Assumption', '', e.assumption, '');
  if (e.caveat) lines.push('## Caveat', '', e.caveat, '');
  if (e.nextStep) lines.push('## Suggested next step', '', e.nextStep, '');
  return lines.join('\n');
}

export function download(filename: string, content: string, type = 'text/plain') {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}
