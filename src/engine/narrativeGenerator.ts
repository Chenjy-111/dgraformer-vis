import type { SampleData } from '@/types/demo';
import type { Explanation, ExplanationDepth } from '@/types/explanation';
import { horizonErrorGrowth, targetMetrics } from './errorDiagnosis';

export interface NarrativeReport {
  title: string;
  sections: { heading: string; body: string }[];
}

function edgeStats(sample: SampleData, windowIdx: number, target: number) {
  const win = sample.windows[windowIdx];
  const all = win.edges.filter((e) => e.source === target || e.target === target);
  const kept = all.filter((e) => e.kept);
  const filtered = all.filter((e) => !e.kept);
  const sorted = [...all].sort((a, b) => b.weight - a.weight);
  const strongest = sorted[0];
  const partner = strongest
    ? sample.variables[strongest.source === target ? strongest.target : strongest.source]
    : null;
  return { all, kept, filtered, strongest, partner };
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
  const tm = targetMetrics(sample, target);
  const es = edgeStats(sample, windowIdx, target);
  const brief = depth === 'brief';
  const tech = depth === 'technical';

  const sections: { heading: string; body: string }[] = [];

  // ── 1. Selected case (all depths) ──
  sections.push({
    heading: '1. Selected case',
    body:
      `Dataset ${sample.dataset}, sample ${sample.sample_id}, prediction horizon ${sample.horizon} steps. ` +
      `Target variable: ${v}. The ${sample.windowSize * sample.windows.length}-step look-back is partitioned into ` +
      `${sample.windows.length} windows of ${sample.windowSize} steps each. ` +
      `Current window ${windowIdx + 1} spans steps ${win.start}–${win.end}.`,
  });

  // ── 2. Forecast summary (all depths) ──
  const forecastBody =
    `Per-variable metrics for ${v}: MSE ${tm.mse.toFixed(4)}, MAE ${tm.mae.toFixed(4)}. ` +
    `Error grows from ${growth.early.toFixed(3)} (first half of horizon) to ${growth.late.toFixed(3)} (second half), ` +
    `a ${(((growth.late - growth.early) / Math.max(0.001, growth.early)) * 100).toFixed(0)}% increase reflecting ` +
    `information decay and uncertainty accumulation over longer horizons.`;
  sections.push({
    heading: '2. Forecast summary',
    body: tech
      ? forecastBody +
        ` The full-sample metrics (all variables) are MSE ${sample.metrics.mse.toFixed(4)}, MAE ${sample.metrics.mae.toFixed(4)}. ` +
        `Error accumulation is monotonic: each additional step into the future adds irreducible uncertainty as the model's ` +
        `observable evidence (look-back window) recedes further from the target.`
      : forecastBody,
  });

  // ── 3. Dynamic graph (all depths) ──
  const graphBrief =
    `In window ${windowIdx + 1}, the dynamic graph contains ${win.edges.length} directed edges among ` +
    `${sample.variables.length} variables. ` +
    `${v} participates in ${es.all.length} edges — ${es.kept.length} retained, ${es.filtered.length} filtered ` +
    `by Top-K focusing (window sparsity ${Math.round(win.sparsity_ratio * 100)}%). ` +
    (es.strongest
      ? `Its strongest correlation is with ${es.partner} (weight ${es.strongest.weight.toFixed(3)}, rank ${es.strongest.rank}).`
      : `It has no edges in this window.`);

  sections.push({
    heading: '3. Dynamic graph',
    body: tech
      ? graphBrief +
        `\n\nThe Dynamic Correlation Graph Learner (DCGL) constructs window-specific adjacency matrices via ` +
        `E_w = α·C + (1−α)·R_w. The static prior C captures seasonal Fourier correlations; ` +
        `the learnable residual R_w adapts to short-term coupling changes via 7 trainable embedding pairs ` +
        `(d_graph=30). Two graph convolution layers (mp_layers=2) propagate features along retained edges. ` +
        `Window-level mean absolute error: ${win.mean_error.toFixed(3)}.`
      : graphBrief,
  });

  if (brief) {
    sections.push({
      heading: '4. Takeaway',
      body:
        `DGraFormer adapts inter-variable correlations per time window, applies Top-K focusing to suppress noise, ` +
        `and processes temporal patterns at three patch scales. For ${v} on ${sample.dataset}, ` +
        `${es.kept.length} of ${es.all.length} connections survive sparsification in window ${windowIdx + 1}. ` +
        `Switch windows or variables to compare how the graph and error profile change.`,
    });
    return { title: `Report — ${sample.dataset} / ${v}`, sections };
  }

  // ── 4. Top-K focusing (standard + technical) ──
  const topkBody =
    `Top-K focusing retains the strongest edges and masks the rest to zero: Ẽ_w = M_w ⊙ E_w. ` +
    `In window ${windowIdx + 1}, the mask keeps ${win.kept_edges.length} of ${win.edges.length} edges ` +
    `(sparsity ${Math.round(win.sparsity_ratio * 100)}%). ` +
    `For ${v} specifically: ${es.kept.length} edges kept (${es.kept.length > 0 ? es.kept.map((e) => sample.variables[e.source === target ? e.target : e.source] + '(' + e.weight.toFixed(2) + ')').join(', ') : 'none'}), ` +
    `${es.filtered.length} filtered.`;
  sections.push({
    heading: tech ? '4. Top-K focusing (ECF)' : '4. Top-K focusing',
    body: tech
      ? topkBody +
        `\n\nEssential Correlation Focusing (ECF) applies a binary mask M_w derived from top-K_e ranking of ` +
        `flattened edge weights. K_e = ⌈w_ratio × N(N−1)⌉. Discarded edges are treated as noise; ` +
        `only retained edges participate in graph message passing (DCGL).`
      : topkBody,
  });

  // ── 5. Multi-scale attention (standard + technical) ──
  const s1 = sample.attention.scale_1;
  const s2 = sample.attention.scale_2;
  const s3 = sample.attention.scale_3;
  sections.push({
    heading: tech ? '5. Multi-scale Transformer (MTT)' : '5. Multi-scale attention',
    body: tech
      ? `The Multi-scale Transformer Encoder processes patches at three resolutions:\n` +
        `• Scale 1 — ${s1.patchSteps}-step patches, ${s1.nPatches} patches: ${s1.semantic}.\n` +
        `• Scale 2 — ${s2.patchSteps}-step patches, ${s2.nPatches} patches: ${s2.semantic}.\n` +
        `• Scale 3 — ${s3.patchSteps}-step patches, ${s3.nPatches} patches: ${s3.semantic}.\n\n` +
        `Each scale uses a dedicated Transformer encoder (d_model=16→32→64, n_heads=4). ` +
        `Between scales, patches are merged (concat adjacent pairs, doubling feature dim) — a hierarchical ` +
        `design that captures short-term fluctuations, periodic patterns, and long-range trends simultaneously.`
      : `Three temporal scales: ${s1.patchSteps}-step (${s1.semantic}), ${s2.patchSteps}-step (${s2.semantic}), ` +
        `${s3.patchSteps}-step (${s3.semantic}). Hierarchical merging combines local and global evidence.`,
  });

  // ── 6. Error diagnosis (standard + technical) ──
  const firstHalf = sample.error[target]?.slice(0, sample.horizon / 2) ?? [];
  const secondHalf = sample.error[target]?.slice(sample.horizon / 2) ?? [];
  const maxEarly = firstHalf.length > 0 ? Math.max(...firstHalf) : 0;
  const maxLate = secondHalf.length > 0 ? Math.max(...secondHalf) : 0;
  sections.push({
    heading: tech ? '6. Error diagnosis (per-step)' : '6. Error diagnosis',
    body: tech
      ? `Per-step absolute error for ${v} ranges from ${Math.min(...sample.error[target]).toFixed(4)} to ` +
        `${Math.max(...sample.error[target]).toFixed(4)}. Early-horizon peak: ${maxEarly.toFixed(3)}; ` +
        `late-horizon peak: ${maxLate.toFixed(3)}. Window ${windowIdx + 1} mean error: ${win.mean_error.toFixed(3)}.\n\n` +
        `Larger errors late in the horizon are expected (information decay). Spikes in specific windows ` +
        `may correlate with graph instability — when the dynamic graph shifts substantially between adjacent ` +
        `windows, the model's representation can become less stable, amplifying error.`
      : `Error for ${v} peaks at ${Math.max(...sample.error[target]).toFixed(3)}. ` +
        `Late-horizon max (${maxLate.toFixed(3)}) exceeds early-horizon max (${maxEarly.toFixed(3)}), ` +
        `consistent with accumulating uncertainty. Current window mean error: ${win.mean_error.toFixed(3)}.`,
  });

  // ── 7. Evidence (standard + technical) ──
  const evidenceLines: string[] = [];
  evidenceLines.push(`Dataset: ${sample.dataset} | Horizon: ${sample.horizon} | Variable: ${v}`);
  evidenceLines.push(`Window: ${windowIdx + 1}/${sample.windows.length} (steps ${win.start}–${win.end})`);
  evidenceLines.push(`MSE (${v}): ${tm.mse.toFixed(4)} | MAE (${v}): ${tm.mae.toFixed(4)}`);
  evidenceLines.push(`Early error: ${growth.early.toFixed(3)} | Late error: ${growth.late.toFixed(3)}`);
  evidenceLines.push(`Window edges: ${win.edges.length} total | ${win.kept_edges.length} kept | ${win.filtered_edges.length} filtered`);
  evidenceLines.push(`Target edges (${v}): ${es.all.length} total | ${es.kept.length} kept | ${es.filtered.length} filtered`);
  evidenceLines.push(`Sparsity: ${Math.round(win.sparsity_ratio * 100)}% | Mean error: ${win.mean_error.toFixed(3)}`);
  evidenceLines.push(`Patch: ${sample.patchLen} steps | Patches per scale: ${s1.nPatches} / ${s2.nPatches} / ${s3.nPatches}`);
  sections.push({
    heading: tech ? '7. Evidence' : '7. Evidence',
    body: evidenceLines.join('\n'),
  });

  // ── 8. Model architecture (technical only) ──
  if (tech) {
    sections.push({
      heading: '8. Model architecture',
      body:
        `DGraFormer components and configuration:\n` +
        `• RevIN: Reversible instance normalization (affine=False, subtract_last=False).\n` +
        `• DCGL: Dynamic graph learner with static Fourier prior + 7 learnable embedding pairs (d_graph=30). ` +
        `Two graph convolution layers (mp_layers=2, d_gcn=1) with proportional propagation (β=0.05).\n` +
        `• ECF: Top-K focusing with w_ratio=0.5, keeping strongest 50% of edges per window.\n` +
        `• Patching: patch_len=${sample.patchLen}, stride=${sample.patchLen}, producing ${s1.nPatches} patches from ${sample.windowSize * sample.windows.length}-step look-back.\n` +
        `• MTT: 3-stage hierarchical Transformer (d_model=16→32→64, n_heads=4, e_layers=1, d_ff=128).\n` +
        `• Predictor: Flatten + Linear(${sample.variables.length}×d_model×patch_num, ${sample.horizon}).\n` +
        `• Loss: 0.5×MSE + 0.5×L1 (CustomLoss). Adam optimizer, lr=1e-4, OneCycleLR scheduler.`,
    });
  }

  // ── Final: Takeaway ──
  sections.push({
    heading: tech ? '9. Takeaway' : '8. Takeaway',
    body:
      `DGraFormer achieves its gains through three mechanisms: (1) DCGL learns window-adaptive correlation graphs ` +
      `instead of a single static graph; (2) Top-K focusing prunes weak edges to suppress noise in message passing; ` +
      `(3) MTT captures temporal patterns at fine, medium, and coarse resolutions. For ${v} in window ${windowIdx + 1}, ` +
      `${es.kept.length} of ${es.all.length} target connections survive focusing — ` +
      (es.kept.length === 0
        ? `this variable is isolated here, relying on its own history via the Transformer rather than graph aggregation.`
        : `the strongest being ${es.partner} at weight ${es.strongest?.weight.toFixed(3)}.`) +
      '',
  });

  return { title: `Report — ${sample.dataset} / ${v}`, sections };
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
  if (e.formula) lines.push('## Formula', '', e.formula.replace(/<[^>]*>/g, ''), '');
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
