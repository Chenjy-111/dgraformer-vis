import type { GraphEdge, SampleData, ScaleId, ViewMode } from '@/types/demo';
import type { Explanation, ExplanationDepth } from '@/types/explanation';
import { classifyNodeRole, edgeStabilityAcrossWindows, nodeDegree } from './graphAnalysis';
import { attentionConcentration, getScale, headMatrix, patchRange } from './attentionAnalysis';
import { diagnose, horizonErrorGrowth, targetMetrics } from './errorDiagnosis';

let idSeq = 0;
const newId = () => `exp-${++idSeq}`;

interface Ctx {
  sample: SampleData;
  windowIdx: number;
  target: number;
  depth: ExplanationDepth;
  scale: ScaleId;
  head: number;
}

function trim(summary: string, depth: ExplanationDepth): string {
  if (depth === 'brief') return summary.split('. ').slice(0, 1).join('. ') + '.';
  return summary;
}

export function buildForecastExplanation(ctx: Ctx): Explanation {
  const { sample, target, depth } = ctx;
  const v = sample.variables[target];
  const growth = horizonErrorGrowth(sample, target);
  const tm = targetMetrics(sample, target);
  const summary =
    `The forecast for ${v} on ${sample.dataset} (horizon ${sample.horizon}) follows the ground truth closely in the ` +
    `near term and drifts gradually further out. Mean absolute error rises from ${growth.early} early in the horizon ` +
    `to ${growth.late} late, reflecting information decay and error accumulation over longer horizons.`;
  return {
    id: newId(),
    title: `Forecast for ${v}`,
    mode: 'forecast',
    selectionLabel: `${sample.dataset} · sample ${sample.sample_id} · h${sample.horizon} · ${v}`,
    summary: trim(summary, depth),
    evidence: [
      { label: `MSE (${v})`, value: String(tm.mse) },
      { label: `MAE (${v})`, value: String(tm.mae) },
      { label: 'Early-horizon error', value: String(growth.early) },
      { label: 'Late-horizon error', value: String(growth.late), tone: 'warn' },
      { label: 'Look-back windows', value: String(sample.windows.length) },
    ],
    formula: 'Y = {x_{T+1}, ..., x_{T+\\tau}}  with  X = {x_1, ..., x_T}',
    assumption: 'The displayed curves are precomputed model outputs; the demo does not run inference in the browser.',
    caveat: 'Per-sample numbers are deterministic mock values calibrated to the reported dataset-level metrics, not exact paper outputs.',
    nextStep: 'Click a high-error segment to jump to its look-back window and inspect the dynamic graph there.',
    quality: { evidence: 0.7, specificity: 0.6, mechanism: 0.5, uncertainty: 0.8 },
  };
}

export function buildEdgeExplanation(ctx: Ctx, edge: GraphEdge): Explanation {
  const { sample, windowIdx, target, depth } = ctx;
  const win = sample.windows[windowIdx];
  const s = sample.variables[edge.source];
  const t = sample.variables[edge.target];
  const stability = edgeStabilityAcrossWindows(sample, edge.source, edge.target);
  const relatedTarget = edge.source === target || edge.target === target;
  const kept = win.kept_edges.some((e) => e.source === edge.source && e.target === edge.target);

  const summary = kept
    ? `${s} \u2192 ${t} is among the top-ranked dynamic correlations in window ${windowIdx + 1} ` +
      `(rank ${edge.rank} of ${win.edges.length}, weight ${edge.weight.toFixed(2)}). DGraFormer keeps it after Top-K ` +
      `focusing, so information from ${s} is propagated to ${t} during graph message passing.`
    : `${s} \u2192 ${t} is a lower-ranked correlation in window ${windowIdx + 1} ` +
      `(rank ${edge.rank} of ${win.edges.length}, weight ${edge.weight.toFixed(2)}). Top-K focusing filters it out, ` +
      `treating it as a weak or possibly spurious relationship that would otherwise inject noise into message passing.`;

  return {
    id: newId(),
    title: kept ? `Why is ${s} \u2192 ${t} retained in this window?` : `Why is ${s} \u2192 ${t} filtered in this window?`,
    mode: 'topk',
    selectionLabel: `Window ${windowIdx + 1} · edge ${s} \u2192 ${t}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Edge weight', value: edge.weight.toFixed(2), tone: kept ? 'kept' : 'filtered' },
      { label: 'Rank in window', value: `${edge.rank} / ${win.edges.length}` },
      { label: 'Status', value: kept ? 'Kept (essential)' : 'Filtered (noise)', tone: kept ? 'kept' : 'filtered' },
      { label: 'Stability across windows', value: `${Math.round(stability * 100)}% of windows` },
      { label: 'Related to target', value: relatedTarget ? `yes (${sample.variables[target]})` : 'no' },
      { label: 'Window mean error', value: String(win.mean_error) },
    ],
    formula: kept
      ? '\\tilde{E}_w = M_w \\odot E_w,  with  E_w = \\alpha C + (1-\\alpha) R_w'
      : 'M_w = top\\text{-}K_e( vec(E_w) ) ; filtered if rank > K_e',
    assumption: 'Edge weight is interpreted as learned correlation strength used for representation aggregation, not causal influence.',
    caveat: kept
      ? 'A retained edge does not prove that ' + s + ' causes ' + t + '. It indicates the model found this relationship useful.'
      : 'A filtered edge is not guaranteed to be noise; Top-K trades a small risk of dropping useful edges for noise reduction.',
    nextStep: 'Compare this edge across adjacent windows to see whether the relationship is stable or temporary.',
    quality: { evidence: 0.85, specificity: 0.9, mechanism: 0.8, uncertainty: 0.85 },
  };
}

export function buildNodeExplanation(ctx: Ctx, node: number): Explanation {
  const { sample, windowIdx, depth } = ctx;
  const win = sample.windows[windowIdx];
  const v = sample.variables[node];
  const deg = nodeDegree(win.kept_edges, node);
  const role = classifyNodeRole(win.kept_edges, node, sample.variables.length);
  const summary =
    `In window ${windowIdx + 1}, ${v} acts as a ${role}. After Top-K focusing it has ${deg.out} outgoing and ` +
    `${deg.in} incoming retained correlations, with total outgoing strength ${deg.strength}. These retained ` +
    `neighbours are the variables whose features are aggregated toward (or from) ${v}.`;
  return {
    id: newId(),
    title: `Role of ${v} in window ${windowIdx + 1}`,
    mode: 'graph',
    selectionLabel: `Window ${windowIdx + 1} · node ${v}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Variable', value: v },
      { label: 'Outgoing retained edges', value: String(deg.out), tone: 'kept' },
      { label: 'Incoming retained edges', value: String(deg.in) },
      { label: 'Outgoing strength', value: String(deg.strength) },
      { label: 'Role', value: role },
    ],
    assumption: 'Roles are derived from the sparsified graph of the current window only.',
    caveat: 'An isolated node in one window may still be correlated in others; inspect the window evolution.',
    nextStep: 'Play the window evolution to see how this variable\u2019s connectivity changes over time.',
    quality: { evidence: 0.78, specificity: 0.82, mechanism: 0.7, uncertainty: 0.7 },
  };
}

export function buildWindowExplanation(ctx: Ctx): Explanation {
  const { sample, windowIdx, depth } = ctx;
  const win = sample.windows[windowIdx];
  const summary =
    win.explanation +
    ` The window spans look-back steps ${win.start}\u2013${win.end}. Sparsity after focusing is ` +
    `${Math.round(win.sparsity_ratio * 100)}% and the window mean error is ${win.mean_error}.`;
  return {
    id: newId(),
    title: `Window ${windowIdx + 1} dynamic graph`,
    mode: 'graph',
    selectionLabel: `Window ${windowIdx + 1} of ${sample.windows.length}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Window span', value: `${win.start}\u2013${win.end}` },
      { label: 'Directed edges', value: String(win.edges.length) },
      { label: 'Kept edges', value: String(win.kept_edges.length), tone: 'kept' },
      { label: 'Filtered edges', value: String(win.filtered_edges.length), tone: 'filtered' },
      { label: 'Sparsity', value: `${Math.round(win.sparsity_ratio * 100)}%` },
      { label: 'Window mean error', value: String(win.mean_error) },
    ],
    formula: 'E_w = \\alpha C + (1-\\alpha) R_w',
    assumption: 'Each window learns its own correlation graph; windows are assumed locally stable.',
    caveat: 'Window sizing here is chosen for visualization (3\u20138 windows). In the paper, m equals one day for the dataset.',
    nextStep: 'Switch to the Top-K Focusing view to see which edges survive sparsification.',
    quality: { evidence: 0.8, specificity: 0.78, mechanism: 0.82, uncertainty: 0.7 },
  };
}

export function buildPatchExplanation(ctx: Ctx, q: number, k: number): Explanation {
  const { sample, scale, head, depth, target } = ctx;
  const s = getScale(sample, scale);
  const mat = headMatrix(s, head);
  const w = mat[q]?.[k] ?? 0;
  const [qs, qe] = patchRange(s, q);
  const [ks, ke] = patchRange(s, k);
  const conc = attentionConcentration(mat);
  const semantic = s.semantic;
  const summary =
    `At scale ${scale} (${s.patchSteps}-step patches), query patch P${q + 1} (steps ${qs}\u2013${qe}) attends to ` +
    `key patch P${k + 1} (steps ${ks}\u2013${ke}) with weight ${w.toFixed(3)}. ${semantic} ` +
    `The head\u2019s overall self-attention concentration is ${conc}.`;
  return {
    id: newId(),
    title: `Attention link P${q + 1} \u2192 P${k + 1} (scale ${scale})`,
    mode: 'attention',
    selectionLabel: `Scale ${scale} · ${head < 0 ? 'mean' : 'head ' + head} · ${sample.variables[target]}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Attention weight', value: w.toFixed(3) },
      { label: 'Query range', value: `${qs}\u2013${qe}` },
      { label: 'Key range', value: `${ks}\u2013${ke}` },
      { label: 'Scale semantics', value: scale === 1 ? 'short-term' : scale === 2 ? 'periodic' : 'long-range' },
      { label: 'Concentration', value: String(conc) },
    ],
    formula: 'z_a = softmax( Q K^\\top / \\sqrt{d_k} ) V',
    assumption: 'Attention is read at the patch level; higher weight means more temporal evidence drawn from the key patch.',
    caveat: 'Attention weights are correlational summaries, not a guarantee of which patch determined the prediction.',
    nextStep: 'Compare the same patch link across scales 1\u20133 to see local vs. periodic vs. trend behaviour.',
    quality: { evidence: 0.75, specificity: 0.85, mechanism: 0.78, uncertainty: 0.8 },
  };
}

export function buildErrorExplanation(ctx: Ctx, step: number): Explanation {
  const { sample, target, depth } = ctx;
  const v = sample.variables[target];
  const clues = diagnose(sample, target, step);
  const err = sample.error[target]?.[step] ?? 0;
  const summary =
    `At future step ${step}, the absolute error for ${v} is ${err.toFixed(3)}. ` +
    `Diagnostic clues (correlational, not causal): ${clues[0]}`;
  return {
    id: newId(),
    title: `Error diagnosis at step ${step}`,
    mode: 'error',
    selectionLabel: `${v} · future step ${step}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Absolute error', value: err.toFixed(3), tone: 'warn' },
      ...clues.slice(0, 4).map((c) => ({ label: 'Clue', value: c })),
    ],
    assumption: 'Diagnosis combines precomputed model-internal signals with the observed error.',
    caveat: 'These are diagnostic clues, not strict causal explanations of the error.',
    nextStep: 'Open the dynamic graph for the nearest window and check for unstable or over-filtered edges.',
    quality: { evidence: 0.6, specificity: 0.7, mechanism: 0.55, uncertainty: 0.9 },
  };
}

const ABLATION_META: Record<string, {
  whatItDoes: string;
  whyItHurts: string;
  formula: string;
  rank: string;
}> = {
  Full: {
    whatItDoes:
      'All four components work together: DCGL learns dynamic correlation graphs across time windows, ' +
      'Top-K focusing prunes weak edges to suppress noise, and MTT extracts temporal patterns at three patch scales.',
    whyItHurts: '',
    formula: '\\text{DCGL}(E_w) \\; \\rightarrow \\; \\text{Top-K}(\\tilde{E}_w) \\; \\rightarrow \\; \\text{MTT}(\\text{patch}_1, \\text{patch}_2, \\text{patch}_3)',
    rank: 'baseline',
  },
  'w/o DTW': {
    whatItDoes:
      'Dynamic Time Windows partition the input into m-step windows, each learning its own correlation graph. ' +
      'Without DTW, a single static graph spans all time steps and cannot capture correlations that shift over time ' +
      '(e.g., day vs. night patterns in hourly data).',
    whyItHurts:
      'This causes the largest accuracy drop because temporal correlation drift is the core challenge in multivariate forecasting — ' +
      'variables that are strongly coupled in one period may be weakly coupled in another.',
    formula: '\\text{w/o DTW: } E_{\\text{single}} \\; \\text{replaces} \\; \\{E_{w_1}, E_{w_2}, \\dots, E_{w_k}\\}',
    rank: 'largest degradation',
  },
  'w/o DGL': {
    whatItDoes:
      'Dynamic Graph Learning uses trainable embeddings to learn window-specific correlation matrices ' +
      '(E_w = α·C + (1-α)·R_w). Without DGL, only the static Fourier prior C is used. ' +
      'The model loses the ability to adaptively discover correlations from data.',
    whyItHurts:
      'Static priors capture seasonal patterns but miss short-term coupling changes. ' +
      'This is the second-largest drop, confirming that learned dynamic graphs are more informative than hand-crafted priors.',
    formula: '\\text{w/o DGL: } E_w = C \\; \\text{(static Fourier prior only)}',
    rank: 'second-largest degradation',
  },
  'w/o ECF': {
    whatItDoes:
      'Essential Correlation Focusing (Top-K sparsification) retains only the strongest ' +
      'w_ratio fraction of edges per window, discarding weak and potentially noisy correlations. ' +
      'Without ECF, all positive edges participate in message passing, injecting noise into the graph convolution.',
    whyItHurts:
      'Moderate degradation — sparsification is a denoising step. Without it, the model is slightly less robust ' +
      'but can still learn useful representations from the full graph.',
    formula: '\\text{w/o ECF: } \\tilde{E}_w = E_w \\; \\text{(no top-K mask)}',
    rank: 'moderate degradation',
  },
  'w/o MTE': {
    whatItDoes:
      'Multi-scale Transformer Encoding processes patches at three temporal resolutions: ' +
      'fine (single-patch, e.g. 8 steps), medium (merged-patch, 16 steps), and coarse (merged-again, 32 steps). ' +
      'Without MTE, only a single fixed patch size is used, missing patterns at other scales.',
    whyItHurts:
      'Moderate degradation — single-scale Transformers still work reasonably well, ' +
      'but multi-scale encoding consistently improves by capturing both short-term fluctuations and long-range trends.',
    formula: '\\text{w/o MTE: single-scale Transformer instead of 3-stage hierarchical encoder}',
    rank: 'moderate degradation',
  },
};

export function buildAblationExplanation(
  ctx: Ctx,
  variant: string,
  label: string,
  mse: number,
  mae: number,
  fullMse: number,
  fullMae: number,
  note: string
): Explanation {
  const { sample, depth } = ctx;
  const pctMse = ((mse - fullMse) / fullMse * 100);
  const pctMae = ((mae - fullMae) / fullMae * 100);
  const meta = ABLATION_META[variant] ?? ABLATION_META['Full'];

  const summary = variant === 'Full'
    ? `${meta.whatItDoes} Full model MSE=${fullMse.toFixed(3)}, MAE=${fullMae.toFixed(3)} on ${sample.dataset} (h${sample.horizon}). Click any variant below to see what happens when a component is removed.`
    : `${meta.whatItDoes} ${meta.whyItHurts}`;

  return {
    id: newId(),
    title: variant === 'Full' ? 'Full DGraFormer — all components' : `${label} — ${meta.rank}`,
    mode: 'ablation',
    selectionLabel: `${sample.dataset} · h${sample.horizon}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'MSE', value: mse.toFixed(3), tone: variant === 'Full' ? 'kept' : 'warn' },
      { label: 'MAE', value: mae.toFixed(3), tone: variant === 'Full' ? 'kept' : 'warn' },
      { label: 'Δ MSE vs Full', value: variant === 'Full' ? '—' : `+${pctMse.toFixed(1)}%`, tone: 'warn' },
      { label: 'Δ MAE vs Full', value: variant === 'Full' ? '—' : `+${pctMae.toFixed(1)}%`, tone: 'warn' },
      { label: 'Impact rank', value: meta.rank },
    ],
    formula: meta.formula,
    assumption: 'Each variant removes exactly one component while keeping all others at their best settings.',
    caveat: variant === 'Full'
      ? 'Metrics from the published IJCAI-25 paper.'
      : `Degradation = cost of removing this component. Components may interact, so individual contributions are not strictly additive.`,
    nextStep: 'Compare degradation magnitudes to understand which component matters most for this dataset.',
    quality: { evidence: 0.92, specificity: 0.88, mechanism: 0.9, uncertainty: 0.75 },
  };
}

export function buildDefaultForView(ctx: Ctx, view: ViewMode): Explanation {
  switch (view) {
    case 'forecast':
      return buildForecastExplanation(ctx);
    case 'graph':
      return buildWindowExplanation(ctx);
    case 'topk':
      return buildWindowExplanation(ctx);
    case 'attention':
      return buildPatchExplanation(ctx, 0, 0);
    case 'error':
      return buildErrorExplanation(ctx, Math.floor(ctx.sample.horizon / 2));
    default:
      return buildForecastExplanation(ctx);
  }
}
