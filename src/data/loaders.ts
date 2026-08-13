import type { DatasetId, Horizon, ModelId, SampleData, GraphEdge, WindowData } from '@/types/demo';

const cache = new Map<string, SampleData>();

function key(d: DatasetId, s: number, h: Horizon) {
  return `${d}_${String(s).padStart(3, '0')}_h${h}`;
}

/**
 * Loads a precomputed sample artifact from public/data/samples/.
 * Each JSON file must conform to the SampleData schema and be exported
 * via scripts/export_demo_data.py from real DGraFormer inference runs.
 */
let msgnetCatalog: any = null;

export async function loadSample(dataset: DatasetId, sampleId: number, horizon: Horizon, model: ModelId = 'DGraFormer'): Promise<SampleData> {
  if (model === 'MSGNet') return loadMSGNetSample(sampleId);
  const k = key(dataset, sampleId, horizon);
  const cached = cache.get(k);
  if (cached) return cached;

  const base = import.meta.env.BASE_URL ?? '/';
  const res = await fetch(`${base}data/samples/${k}.json`);
  if (!res.ok) {
    throw new Error(
      `Sample data not found: ${k}.json. Run scripts/export_demo_data.py to export real DGraFormer inference artifacts.`
    );
  }
  const json = (await res.json()) as SampleData;
  cache.set(k, json);
  return json;
}

async function loadMSGNetSample(sampleId: number): Promise<SampleData> {
  const base = import.meta.env.BASE_URL ?? '/';
  if (!msgnetCatalog) {
    const response = await fetch(`${base}data/models/msgnet/etth1/catalog.json`);
    if (!response.ok) throw new Error('Audited MSGNet catalog is unavailable.');
    msgnetCatalog = await response.json();
  }
  const raw = msgnetCatalog.samples[sampleId];
  if (!raw) throw new Error(`MSGNet sample ${sampleId} is unavailable.`);
  const edges = (matrix: number[][]): GraphEdge[] => matrix.flatMap((row, source) => row.map((weight, target) => ({ source, target, weight, rank: 0, kept: source !== target }))).filter((e) => e.source !== e.target).sort((a,b)=>b.weight-a.weight).map((e,i)=>({...e,rank:i+1}));
  const windows: WindowData[] = raw.contexts.map((context: any) => {
    const all = edges(context.effective);
    return { window_id: context.scale_index, start: 0, end: 96, static_graph: context.adaptive,
      dynamic_graph: context.adaptive, sparse_graph: context.effective, edges: all, kept_edges: all,
      filtered_edges: [], top_edges: all.slice(0, 10), sparsity_ratio: 0, mean_error: null,
      explanation: `MSGNet period-${context.period} scale-conditioned adaptive graph.` };
  });
  const error = raw.prediction.map((series: number[], variable: number) => series.map((value, step) => Math.abs(value - raw.ground_truth[variable][step])));
  return { model: 'MSGNet', dataset: 'ETTh1', sample_id: sampleId, horizon: 96, variables: msgnetCatalog.variables,
    targetDefault: 6, history: raw.history, ground_truth: raw.ground_truth, prediction: raw.prediction, error,
    windows, windowSize: 96, patchLen: 8, attention: {} as SampleData['attention'], metrics: raw.metrics,
    narrative: msgnetCatalog.notice, relationContextKind: 'scale',
    msgnetContexts: raw.contexts.map((c:any)=>({scaleIndex:c.scale_index,period:c.period,fftStrength:c.fft_strength,contribution:c.scale_contribution})),
    msgnetEdgeImpacts: raw.edge_impacts.map((e:any)=>({scaleIndex:e.scale_index,source:e.source,target:e.target,graphWeight:e.adaptive_weight,
      predictionDeltaAbs:e.prediction_delta_abs,errorDeltaMae:e.error_delta_mae,controlMean:e.statistics.control_mean_prediction_delta_abs,
      controlPercentile:e.statistics.control_percentile,empiricalP:e.statistics.empirical_p,bhAdjustedP:e.statistics.bh_adjusted_p})),
    provenance: { scheduleState:'trained checkpoint', currentEpochEquivalent:10, staticWeight:0, learnedWeight:1,
      testSampleIndex:raw.sample_index, checkpointSha256:msgnetCatalog.checkpoint_sha256,dataSha256:'f18de3ad269cef59bb07b5438d79bb3042d3be49bdeecf01c1cd6d29695ee066',runId:msgnetCatalog.evidence_run_id }
  };
}
