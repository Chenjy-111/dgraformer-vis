import type { GraphEdge, SampleData, ScaleId, ViewMode } from '@/types/demo';
import type { Explanation, ExplanationDepth } from '@/types/explanation';
import { edgeStabilityAcrossWindows, recomputeTopK } from './graphAnalysis';
import { attentionConcentration, getScale, headMatrix, patchRange } from './attentionAnalysis';
import { diagnose, horizonErrorGrowth, targetMetrics } from './errorDiagnosis';
import { prender } from '@/utils/katexPrender';

let idSeq = 0;
const newId = () => `exp-${++idSeq}`;

// Pre-render all formula strings at module load time (build time)
const F = {
  forecast: prender('Y = {x_{T+1}, ..., x_{T+\\tau}}  with  X = {x_1, ..., x_T}'),
  edgeKept: prender('\\tilde{E}_w = M_w \\odot E_w,  with  E_w = \\alpha C + (1-\\alpha) R_w'),
  edgeFiltered: prender('M_w = top\\text{-}K_e( vec(E_w) ) ; filtered if rank > K_e'),
  window: prender('E_w = \\alpha C + (1-\\alpha) R_w'),
  attention: prender('z_a = softmax( Q K^\\top / \\sqrt{d_k} ) V'),
  ablationFull: prender('\\text{DCGL}(E_w) \\; \\rightarrow \\; \\text{Top-K}(\\tilde{E}_w) \\; \\rightarrow \\; \\text{MTT}(\\text{patch}_1, \\text{patch}_2, \\text{patch}_3)'),
  ablationNoDTW: prender('\\text{w/o DTW: } E_{\\text{single}} \\; \\text{replaces} \\; \\{E_{w_1}, E_{w_2}, \\dots, E_{w_k}\\}'),
  ablationNoDGL: prender('\\text{w/o DGL: } E_w = C \\; \\text{(static Fourier prior only)}'),
  ablationNoECF: prender('\\text{w/o ECF: } \\tilde{E}_w = E_w \\; \\text{(no top-K mask)}'),
  ablationNoMTE: prender('\\text{w/o MTE: single-scale Transformer instead of 3-stage hierarchical encoder}'),
  topK: prender('\\tilde{E}_w = M_w \\odot E_w, \\quad M_w = \\text{top-}K_e(\\text{vec}(E_w))'),
};

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
  const { sample, target } = ctx;
  const v = sample.variables[target];
  const growth = horizonErrorGrowth(sample, target);
  const tm = targetMetrics(sample, target);
  const firstHalfEnd = Math.floor(sample.horizon / 2);
  const secondHalfStart = firstHalfEnd + 1;
  const summary =
    `For ${sample.dataset} sample ${sample.sample_id}, the ${v} forecast has MAE ${tm.mae} and MSE ${tm.mse} ` +
    `over ${sample.horizon} forecast steps. Mean absolute error is ${growth.early} for steps 1–${firstHalfEnd} ` +
    `and ${growth.late} for steps ${secondHalfStart}–${sample.horizon}.`;
  return {
    id: newId(),
    title: `Forecast for ${v}`,
    mode: 'forecast',
    selectionLabel: `${sample.dataset} · sample ${sample.sample_id} · h${sample.horizon} · ${v}`,
    summary,
    evidence: [
      { label: `MSE (${v})`, value: String(tm.mse) },
      { label: `MAE (${v})`, value: String(tm.mae) },
      { label: `Mean absolute error (steps 1–${firstHalfEnd})`, value: String(growth.early) },
      { label: `Mean absolute error (steps ${secondHalfStart}–${sample.horizon})`, value: String(growth.late) },
      { label: 'Forecast steps', value: String(sample.horizon) },
    ],
    formula: F.forecast,
    assumption: 'The displayed curves are precomputed per-sample model outputs; the demo does not run inference in the browser.',
    caveat: 'Absolute error is computed as |ground truth − prediction| for each displayed forecast step.',
  };
}

export function buildForecastStepExplanation(ctx: Ctx, step: number): Explanation {
  const { sample, target } = ctx;
  const variable = sample.variables[target];
  const groundTruth = sample.ground_truth[target]?.[step];
  const prediction = sample.prediction[target]?.[step];
  const absoluteError = sample.error[target]?.[step];
  const displayStep = step + 1;

  return {
    id: newId(),
    title: `Forecast step ${displayStep} for ${variable}`,
    mode: 'forecast',
    selectionLabel: `${sample.dataset} · sample ${sample.sample_id} · ${variable} · step ${displayStep}`,
    summary:
      `At forecast step ${displayStep}, the ground truth is ${groundTruth.toFixed(3)}, ` +
      `the prediction is ${prediction.toFixed(3)}, and the absolute error is ${absoluteError.toFixed(3)}.`,
    evidence: [
      { label: 'Ground truth', value: groundTruth.toFixed(3) },
      { label: 'Prediction', value: prediction.toFixed(3) },
      { label: 'Absolute error', value: absoluteError.toFixed(3), tone: 'warn' },
      { label: 'Forecast step', value: `${displayStep} / ${sample.horizon}` },
    ],
    caveat: 'Absolute error is computed as |ground truth − prediction| from the displayed precomputed output.',
  };
}

export function buildEdgeExplanation(ctx: Ctx, edge: GraphEdge): Explanation {
  const { sample, windowIdx, target, depth } = ctx;
  const win = sample.windows[windowIdx];
  const s = sample.variables[edge.source];
  const t = sample.variables[edge.target];
  const stability = edgeStabilityAcrossWindows(sample, edge.source, edge.target);
  const relatedTarget = edge.source === target || edge.target === target;
  const weight = win.dynamic_graph[edge.source]?.[edge.target] ?? edge.weight;
  const ranked = win.edges.find((e) => e.source === edge.source && e.target === edge.target);
  const rank = ranked?.rank ?? edge.rank;
  const summary =
    `${s} \u2192 ${t} has learned weight ${weight.toFixed(3)} in the real dynamic adjacency matrix for ` +
    `window ${windowIdx + 1}. Its rank among ${win.edges.length} directed off-diagonal entries is ${rank}. ` +
    `This is a model-learned association strength, not evidence of causality.`;

  return {
    id: newId(),
    title: `${s} \u2192 ${t} in window ${windowIdx + 1}`,
    mode: 'graph',
    selectionLabel: `Window ${windowIdx + 1} · edge ${s} \u2192 ${t}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Dynamic edge weight', value: weight.toFixed(3) },
      { label: 'Rank in current matrix', value: `${rank} / ${win.edges.length}` },
      { label: 'Stability across windows', value: `${Math.round(stability * 100)}% of windows` },
      { label: 'Related to target', value: relatedTarget ? `yes (${sample.variables[target]})` : 'no' },
      { label: 'Window mean error', value: String(win.mean_error) },
    ],
    assumption: 'Edge weight is interpreted as learned correlation strength used for representation aggregation, not causal influence.',
    caveat: 'The rank is computed directly from the exported dynamic matrix; it does not by itself imply that an edge was retained by a training-time mask.',
    nextStep: 'Compare this edge across adjacent windows to see whether the relationship is stable or temporary.',
    quality: { evidence: 0.85, specificity: 0.9, mechanism: 0.8, uncertainty: 0.85 },
  };
}

export function buildNodeExplanation(ctx: Ctx, node: number): Explanation {
  const { sample, windowIdx, depth } = ctx;
  const win = sample.windows[windowIdx];
  const v = sample.variables[node];
  const outgoing = win.dynamic_graph[node]
    .map((weight, target) => ({ target, weight }))
    .filter((item) => item.target !== node)
    .sort((a, b) => b.weight - a.weight);
  const incoming = win.dynamic_graph
    .map((row, source) => ({ source, weight: row[node] }))
    .filter((item) => item.source !== node)
    .sort((a, b) => b.weight - a.weight);
  const strongestOut = outgoing[0];
  const strongestIn = incoming[0];
  const meanOut = outgoing.reduce((sum, item) => sum + item.weight, 0) / Math.max(1, outgoing.length);
  const summary =
    `For ${v} in window ${windowIdx + 1}, the strongest outgoing association is ` +
    `${sample.variables[strongestOut.target]} (${strongestOut.weight.toFixed(3)}), and the strongest incoming ` +
    `association is ${sample.variables[strongestIn.source]} (${strongestIn.weight.toFixed(3)}). ` +
    `These values come directly from the exported dynamic adjacency matrix.`;
  return {
    id: newId(),
    title: `${v} in the dynamic graph`,
    mode: 'graph',
    selectionLabel: `Window ${windowIdx + 1} · node ${v}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Variable', value: v },
      { label: 'Strongest outgoing', value: sample.variables[strongestOut.target] },
      { label: 'Outgoing weight', value: strongestOut.weight.toFixed(3) },
      { label: 'Strongest incoming', value: sample.variables[strongestIn.source] },
      { label: 'Incoming weight', value: strongestIn.weight.toFixed(3) },
      { label: 'Mean outgoing weight', value: meanOut.toFixed(3) },
    ],
    assumption: 'Weights are read from the current window\u2019s exported dynamic graph.',
    caveat: 'Learned graph weights describe model associations, not causal relationships between variables.',
    nextStep: 'Play the window evolution to see how this variable\u2019s connectivity changes over time.',
    quality: { evidence: 0.78, specificity: 0.82, mechanism: 0.7, uncertainty: 0.7 },
  };
}

export function buildWindowExplanation(ctx: Ctx): Explanation {
  const { sample, windowIdx, depth } = ctx;
  const win = sample.windows[windowIdx];
  const weights = win.dynamic_graph.flatMap((row, source) =>
    row.filter((_, target) => source !== target)
  );
  const meanWeight = weights.reduce((sum, weight) => sum + weight, 0) / Math.max(1, weights.length);
  const maxWeight = Math.max(...weights);
  const summary =
    `Window ${windowIdx + 1} spans look-back steps ${win.start}\u2013${win.end}. Its exported dynamic graph ` +
    `contains ${weights.length} directed off-diagonal weights with mean ${meanWeight.toFixed(3)} and maximum ` +
    `${maxWeight.toFixed(3)}. The mean absolute forecast error over the corresponding interval is ${win.mean_error}.`;
  return {
    id: newId(),
    title: `Window ${windowIdx + 1} dynamic graph`,
    mode: 'graph',
    selectionLabel: `Window ${windowIdx + 1} of ${sample.windows.length}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Window span', value: `${win.start}\u2013${win.end}` },
      { label: 'Variables', value: String(sample.variables.length) },
      { label: 'Directed matrix entries', value: String(weights.length) },
      { label: 'Mean dynamic weight', value: meanWeight.toFixed(3) },
      { label: 'Maximum dynamic weight', value: maxWeight.toFixed(3) },
      { label: 'Window mean error', value: String(win.mean_error) },
    ],
    formula: F.window,
    assumption: 'Values are read from the exported dynamic graph for this window.',
    caveat: 'Dynamic graph weights are learned associations and should not be interpreted as causal effects.',
    nextStep: 'Select a variable or edge to inspect its exact weights in this window.',
    quality: { evidence: 0.8, specificity: 0.78, mechanism: 0.82, uncertainty: 0.7 },
  };
}

export function buildPatchExplanation(ctx: Ctx, q: number, k: number): Explanation {
  const { sample, scale, head, depth, target } = ctx;
  const s = getScale(sample, scale);
  const mat = headMatrix(s, head, target);
  const w = mat[q]?.[k] ?? 0;
  const [qs, qe] = patchRange(s, q);
  const [ks, ke] = patchRange(s, k);
  const conc = attentionConcentration(mat);
  const semantic = s.semantic;
  const scaleDescription = scale === 3
    ? `${sample.history[0]?.length ?? 96}-step context`
    : `${s.patchSteps}-step patches`;
  const summary =
    `At scale ${scale} (${scaleDescription}), query patch P${q + 1} (steps ${qs}\u2013${qe}) attends to ` +
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
    formula: F.attention,
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
    formula: F.ablationFull,
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
    formula: F.ablationNoDTW,
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
    formula: F.ablationNoDGL,
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
    formula: F.ablationNoECF,
    rank: 'moderate degradation',
  },
  'w/o MTE': {
    whatItDoes:
      'Multi-scale Transformer Encoding processes patches at three temporal resolutions: ' +
      'fine (single-patch, e.g. 8 steps), medium (merged-patch, 16 steps), and coarse (full 96-step context). ' +
      'Without MTE, only a single fixed patch size is used, missing patterns at other scales.',
    whyItHurts:
      'Moderate degradation — single-scale Transformers still work reasonably well, ' +
      'but multi-scale encoding consistently improves by capturing both short-term fluctuations and long-range trends.',
    formula: F.ablationNoMTE,
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

export function buildTopKExplanation(ctx: Ctx, topkRatio: number): Explanation {
  const { sample, windowIdx, target, depth } = ctx;
  const win = sample.windows[windowIdx];
  const v = sample.variables[target];

  // recompute kept/filtered according to current ratio
  const ratedEdges = recomputeTopK(win.edges, topkRatio);
  const allTargetEdges = ratedEdges.filter((e) => e.source === target || e.target === target);
  const keptTarget = allTargetEdges.filter((e) => e.kept);
  const filteredTarget = allTargetEdges.filter((e) => !e.kept);
  const keptRatio = allTargetEdges.length > 0 ? Math.round((keptTarget.length / allTargetEdges.length) * 100) : 0;

  // strongest edge touching target (by weight)
  const sorted = [...allTargetEdges].sort((a, b) => b.weight - a.weight);
  const strongest = sorted[0];
  const strongPartner = strongest
    ? sample.variables[strongest.source === target ? strongest.target : strongest.source]
    : null;

  const summary =
    `Top-K focusing retains the strongest ${Math.round(topkRatio * 100)}% of edges per window, ` +
    `sparsifying the dynamic graph from ${win.edges.length} edges down to ${Math.round(win.edges.length * topkRatio)}. ` +
    `For ${v}, ${keptTarget.length} of ${allTargetEdges.length} connections are kept (${keptRatio}%), ` +
    (strongest
      ? `and its strongest link is to ${strongPartner} (weight ${strongest.weight.toFixed(2)}, rank ${strongest.rank}).`
      : `and it has no edges in this window.`);

  return {
    id: newId(),
    title: `Top-K focusing for ${v}`,
    mode: 'topk',
    selectionLabel: `${sample.dataset} · window ${windowIdx + 1} · ${v}`,
    summary: trim(summary, depth),
    evidence: [
      { label: 'Target variable', value: v },
      { label: 'Edges touching target', value: String(allTargetEdges.length) },
      { label: 'Kept', value: String(keptTarget.length), tone: 'kept' },
      { label: 'Filtered', value: String(filteredTarget.length), tone: 'filtered' },
      { label: 'Keep ratio (target)', value: `${keptRatio}%` },
      { label: 'Strongest partner', value: strongPartner ?? 'none' },
      { label: 'Window sparsity', value: `${Math.round(win.sparsity_ratio * 100)}%` },
      { label: 'Global keep ratio', value: `${Math.round(topkRatio * 100)}%` },
    ],
    formula: F.topK,
    assumption: `Top-K ratio ${Math.round(topkRatio * 100)}% means only the top ${Math.round(topkRatio * 100)}% of edges by weight are retained per window; all others are masked to zero.`,
    caveat: keptTarget.length === 0
      ? `${v} has no edges surviving Top-K in this window — it may be weakly correlated with other variables here, or correlations are distributed across many weak edges.`
      : `Edge counts reflect the sparsified graph after Top-K. A kept edge means the model found this correlation useful; it does not imply causality.`,
    nextStep: 'Click a kept edge to see why it was retained, or a filtered one to understand why it was dropped.',
    quality: { evidence: 0.82, specificity: 0.85, mechanism: 0.78, uncertainty: 0.75 },
  };
}

export function buildDefaultForView(ctx: Ctx, view: ViewMode): Explanation {
  switch (view) {
    case 'forecast':
      return buildForecastExplanation(ctx);
    case 'graph':
      return buildWindowExplanation(ctx);
    case 'topk':
      return buildTopKExplanation(ctx, 0.4);
    case 'attention':
      return buildPatchExplanation(ctx, 0, 0);
    case 'error':
      return buildErrorExplanation(ctx, Math.floor(ctx.sample.horizon / 2));
    default:
      return buildForecastExplanation(ctx);
  }
}
