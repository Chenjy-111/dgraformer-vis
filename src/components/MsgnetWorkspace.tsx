import { useEffect, useState, type ReactNode } from 'react';
import { LoaderCircle } from 'lucide-react';
import { GraphNetwork } from './charts/GraphNetwork';
import { getMsgnetEvidenceIndex, loadMsgnetCatalog, type MsgnetCatalog, type MsgnetSample } from '@/data/msgnetLoader';
import type { GraphEdge, SampleData, WindowData } from '@/types/demo';
import { ForecastChart } from './ForecastChart';
import { Select } from './ui/Select';
import { Tabs } from './ui/Tabs';
import { Slider } from './ui/Slider';
import { Toggle } from './ui/Toggle';
import { MsgnetScaleGraph3D } from './three/MsgnetScaleGraph3D';
import { useWorkflowStore } from '@/store/useWorkflowStore';

function useMsgnet() {
  const [catalog, setCatalog] = useState<MsgnetCatalog | null>(null);
  const [failure, setFailure] = useState('');
  useEffect(() => { loadMsgnetCatalog().then(setCatalog).catch((error: Error) => setFailure(error.message)); }, []);
  return { catalog, failure };
}

export function MsgnetDataWorkspace() {
  const selectRelation = useWorkflowStore(state => state.selectRelation);
  const clearSelection = useWorkflowStore(state => state.setModel);
  const { catalog, failure } = useMsgnet();
  const [sampleId, setSampleId] = useState(0);
  const [variable, setVariable] = useState(6);
  const [view, setView] = useState<'forecast' | 'graph'>('graph');
  const [scale, setScale] = useState(0);
  const [layout, setLayout] = useState<'heatmap' | 'network' | '3d'>('heatmap');
  const [selected, setSelected] = useState<{ source: number; target: number } | null>(null);
  const [patches, setPatches] = useState(true);

  if (!catalog) return <div className={`flex min-h-[320px] items-center justify-center ${failure ? 'text-red-700' : 'text-ink-400'}`}>{failure || <><LoaderCircle className="mr-2 animate-spin" size={18}/>Loading MSGNet graph artifacts…</>}</div>;
  const sample = catalog.samples[sampleId];
  const context = sample.contexts[scale];
  const edges = matrixEdges(context.adaptive);
  const adapted = adaptSample(catalog, sample);
  const variableEvidence = getMsgnetEvidenceIndex(sample).variables[String(variable)];

  const changeScale = (value: number) => { setScale(value); setSelected(null); clearSelection('MSGNet'); };
  const pick = (source: number, target: number, selectedScale = scale) => {
    setScale(selectedScale);
    setSelected({ source, target });
    selectRelation({ model: 'MSGNet', dataset: 'ETTh1', sample: sample.sample_index, contextType: 'scale', contextIndex: selectedScale, source, target, sourceName: catalog.variables[source], targetName: catalog.variables[target] });
  };

  return <div className="border-b border-line bg-white"><div className="mx-auto grid max-w-[1400px] gap-6 px-5 py-14 lg:grid-cols-[280px_1fr_320px]">
    <aside className="space-y-5"><Group label="Case"><div className="space-y-2.5"><Field label="Dataset"><Select value="ETTh1" onChange={() => {}} options={[{ value: 'ETTh1', label: 'ETTh1 · 7 vars' }]} ariaLabel="MSGNet dataset"/></Field><Field label="Target variable"><Select value={variable} onChange={setVariable} options={catalog.variables.map((label, value) => ({ value, label }))} ariaLabel="MSGNet target variable"/></Field><Field label="Prediction horizon"><Tabs value={96} onChange={() => {}} options={[{ value: 96, label: '96' }]} size="sm"/></Field></div></Group><Group label="View"><Tabs value={view} onChange={setView} options={[{ value: 'forecast', label: 'Forecast' }, { value: 'graph', label: 'Dynamic graph' }]} size="sm" wrap/></Group>{view === 'graph' && <Group label="Graph"><Slider label="Scale index" value={scale} min={0} max={2} onChange={changeScale} format={value => `#${value}`}/><Field label="Layout"><Tabs value={layout} onChange={setLayout} options={[{ value: 'heatmap', label: 'Matrix' }, { value: 'network', label: 'Network' }, { value: '3d', label: '3D timeline' }]} size="sm" wrap/></Field></Group>}<Group label="Display"><Toggle checked={patches} onChange={setPatches} label="Show patch boundary"/></Group></aside>
    <main className="card min-h-[540px] p-5">{view === 'forecast' ? <div><div className="mb-3 flex items-center justify-between gap-3"><div className="flex items-center gap-3"><h3 className="whitespace-nowrap text-[15px] font-semibold">Forecast · {catalog.variables[variable]} <span className="text-ink-400">(ETTh1)</span></h3><Select value={sampleId} onChange={value => { setSampleId(value); setSelected(null); clearSelection('MSGNet'); }} options={Object.keys(catalog.samples).map(Number).map(value => ({ value, label: `sample ${value}` }))} ariaLabel="MSGNet sample"/></div><span className="data-num whitespace-nowrap text-[12px] text-ink-400">MSE {sample.metrics.mse.toFixed(6)} · MAE {sample.metrics.mae.toFixed(6)}</span></div><ForecastChart sample={adapted} variable={variable} windowIdx={scale} showPatchBoundary={patches}/><p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">The curve is a stored checkpoint output. Scale selection is independent of forecast residuals.</p></div> : <><div className="flex flex-wrap items-baseline justify-between gap-3"><div><h3 className="text-[15px] font-semibold">Dynamic scale graph · scale_index {scale}</h3><p className="mt-1 text-[11px] font-semibold text-[#176e69]">Click an edge in the graph to inspect its evidence.</p></div><span className="data-num text-[12px] text-ink-400">current sample FFT period {context.period} · stored mixing weight {formatContribution(context.scale_contribution)}</span></div>{layout === 'heatmap' ? <Matrix matrix={context.adaptive} variables={catalog.variables} selected={selected} onPick={pick}/> : layout === 'network' ? <div className="flex justify-center pt-8"><GraphNetwork variables={catalog.variables} edges={edges} layout="circular" showLabels threshold={0} target={variable} highlightTarget selectedNode={null} selectedEdge={selected} onClickEdge={edge => pick(edge.source, edge.target)} size={440}/></div> : <MsgnetScaleGraph3D variables={catalog.variables} contexts={sample.contexts} graphs={sample.contexts.map(item => matrixEdges(item.adaptive))} activeScale={scale} selectedEdge={selected} onSelectScale={changeScale} onSelectEdge={(edge, selectedScale) => pick(edge.source, edge.target, selectedScale)}/>}<p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">Displayed weights are exported from the trained MSGNet checkpoint. Graph filters and scale navigation never change the frozen candidate families or statistics.</p></>}</main>
    <aside className="space-y-4"><div className="flex items-center justify-between"><span className="rounded-full border border-accent/30 bg-accent-soft px-2.5 py-1 text-[10px] font-semibold text-accent">{view === 'forecast' ? 'Forecast artifact' : 'Scale graph artifact'}</span><span className="data-num text-[10px] text-ink-400">sample {sampleId} · scale_index {scale}</span></div><Info label="Stored variable metrics"><EvidenceGrid items={[["Variable", catalog.variables[variable]], ["MSE", variableEvidence.mse.toFixed(6)], ["MAE", variableEvidence.mae.toFixed(6)]]}/></Info><Info label="Stored scale fields"><EvidenceGrid items={[["Scale identity", String(scale)], ["Current FFT period", String(context.period)], ["FFT strength", context.fft_strength.toFixed(6)], ["Mixing weight", formatContribution(context.scale_contribution)]]}/></Info>{selected ? <Info label="Selected graph relation"><div className="text-[13px] font-semibold">{catalog.variables[selected.source]} → {catalog.variables[selected.target]}</div><p className="mt-2 font-mono text-[10px]">weight {context.adaptive[selected.source][selected.target].toFixed(6)}</p><p className="mt-2 text-[9px] text-ink-400">Formal p/q appears only below the graph from Session v2.</p></Info> : <Info label="Selection">No relation selected. Click any directed non-self graph edge.</Info>}<Info label="Data provenance" mono>checkpoint {catalog.checkpoint_sha256.slice(0, 16)}…</Info><Info label="Caveat">Graph and scale weights are model-internal quantities, not functional conclusions or real-world causal claims.</Info></aside>
  </div></div>;
}

function Group({ label, children }: { label: string; children: ReactNode }) { return <div><div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-400">{label}</div>{children}</div>; }
function Field({ label, children }: { label: string; children: ReactNode }) { return <div><div className="mb-1 text-[12px] text-ink-400">{label}</div>{children}</div>; }
function Info({ label, children, mono = false }: { label: string; children: ReactNode; mono?: boolean }) { return <div className="rounded-card border border-line bg-white p-3"><div className="eyebrow mb-1">{label}</div><div className={`text-[12.5px] leading-relaxed text-ink-700 ${mono ? 'font-mono' : ''}`}>{children}</div></div>; }
function EvidenceGrid({ items }: { items: [string, string][] }) { return <div className="grid grid-cols-2 gap-2">{items.map(([label, value]) => <div key={label} className="rounded-md bg-[#f5f7fa] px-2 py-2"><div className="text-[8px] uppercase tracking-wide text-ink-400">{label}</div><div className="mt-1 break-all font-mono text-[10px] font-semibold text-ink-700">{value}</div></div>)}</div>; }
function formatContribution(value: number | number[]) { return Array.isArray(value) ? value.map(item => item.toFixed(4)).join(' · ') : value.toFixed(4); }
function adaptSample(catalog: MsgnetCatalog, sample: MsgnetSample): SampleData { const windows: WindowData[] = sample.contexts.map((context, index) => { const all = matrixEdges(context.adaptive); return { window_id: index, start: index * 32, end: (index + 1) * 32, static_graph: context.adaptive, dynamic_graph: context.adaptive, sparse_graph: context.effective, edges: all, kept_edges: all, filtered_edges: [], top_edges: all.slice(0, 10), sparsity_ratio: 0, mean_error: null, explanation: `MSGNet scale ${index}, period ${context.period}` }; }); return { dataset: 'ETTh1', sample_id: sample.sample_index, horizon: 96, variables: catalog.variables, targetDefault: 6, history: sample.history, ground_truth: sample.ground_truth, prediction: sample.prediction, error: sample.prediction.map((series, variable) => series.map((value, index) => Math.abs(value - sample.ground_truth[variable][index]))), windows, windowSize: 32, patchLen: 8, attention: {} as SampleData['attention'], metrics: sample.metrics, narrative: catalog.notice }; }
function Matrix({ matrix, variables, selected, onPick }: { matrix: number[][]; variables: string[]; selected: { source: number; target: number } | null; onPick: (source: number, target: number) => void }) { const max = Math.max(...matrix.flat(), .001); return <div className="mx-auto mt-8 grid max-w-[560px] gap-1" style={{ gridTemplateColumns: `58px repeat(${variables.length},1fr)` }}><span/>{variables.map(value => <span className="text-center text-[9px] text-ink-400" key={value}>{value}</span>)}{matrix.map((row, source) => <div className="contents" key={source}><span className="flex items-center text-[9px] text-ink-400">{variables[source]}</span>{row.map((value, target) => <button key={target} disabled={source === target} onClick={() => onPick(source, target)} title={`${variables[source]} → ${variables[target]}: ${value.toFixed(4)}`} className={`aspect-square cursor-pointer rounded border transition hover:ring-2 hover:ring-[#16827f]/50 disabled:cursor-default ${selected?.source === source && selected.target === target ? 'border-red-500 ring-2 ring-red-200' : 'border-white'}`} style={{ background: source === target ? '#e8edf0' : `rgba(22,130,127,${.08 + .82 * value / max})` }}/>)}</div>)}</div>; }
function matrixEdges(matrix: number[][]): GraphEdge[] { return matrix.flatMap((row, source) => row.map((weight, target) => ({ source, target, weight, rank: 0, kept: source !== target && weight > 0 }))).filter(edge => edge.source !== edge.target).sort((a, b) => b.weight - a.weight).map((edge, index) => ({ ...edge, rank: index + 1 })); }
