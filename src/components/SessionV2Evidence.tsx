import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Activity, AlertTriangle, BarChart3, CheckCircle2, CircleOff, Info, LoaderCircle, Microscope, ShieldCheck } from 'lucide-react';
import type { AuditSessionV2, AuditTensor, CandidateRelation, CaseEvidence, CrossSampleEvidence, HypothesisFamily, SensitivityResult } from '@/data/auditSessionV2';
import { exactCandidate, exactCase, loadBuiltInSessionV2, relationGroups, sampleById, type CandidateBundle } from '@/data/auditSessionV2View';
import { useDemoStore } from '@/store/useDemoStore';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { Select } from './ui/Select';

type Model = 'DGraFormer' | 'MSGNet';
type Tab = 'summary' | 'single' | 'all' | 'intervention';

function useSession(model: Model, supplied?: AuditSessionV2 | null) {
  const [session, setSession] = useState<AuditSessionV2 | null>(supplied ?? null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (supplied) { setSession(supplied); setError(''); return; }
    let active = true;
    loadBuiltInSessionV2(model).then(value => { if (active) setSession(value); }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [model, supplied]);
  return { session, error };
}

export function DgraSessionV2Evidence({ supplied }: { supplied?: AuditSessionV2 | null }) {
  const { session, error } = useSession('DGraFormer', supplied);
  const graphWindow = useDemoStore(state => state.windowIdx);
  const graphSample = useDemoStore(state => state.sampleId);
  const selectRelation = useWorkflowStore(state => state.selectRelation);
  const [relationKey, setRelationKey] = useState<string | null>(null);
  const [windowId, setWindowId] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>('summary');
  const [sampleId, setSampleId] = useState<number | null>(null);

  const groups = useMemo(() => session ? relationGroups(session) : [], [session]);
  const group = groups.find(item => `${item.source}->${item.target}` === relationKey) ?? null;
  const multiple = (group?.retained.length ?? 0) > 1;
  const local = session && group && windowId !== null ? exactCandidate(session, candidate => candidate.source === group.source && candidate.target === group.target && candidate.scope === 'single_window' && candidate.window_index === windowId) : null;
  const all = session && group ? exactCandidate(session, candidate => candidate.source === group.source && candidate.target === group.target && candidate.scope === 'all_retained_windows') : null;

  useEffect(() => {
    if (!session) return;
    setSampleId(current => current !== null && session.samples.some(sample => sample.sample_index === current) ? current : session.samples[0]?.sample_index ?? null);
  }, [session]);

  if (error) return <LoadFailure error={error}/>;
  if (!session) return <Loading label="Loading frozen DGraFormer Session v2…"/>;

  const choose = (source: number, target: number) => {
    const next = groups.find(item => item.source === source && item.target === target)!;
    const nextWindow = next.retained.includes(graphWindow) ? graphWindow : next.retained[0];
    setRelationKey(`${source}->${target}`);
    setWindowId(nextWindow);
    setTab('summary');
    selectRelation({ model: 'DGraFormer', dataset: String((session.dataset as any).name), sample: graphSample, contextType: 'window', contextIndex: nextWindow, source, target, sourceName: next.sourceName, targetName: next.targetName });
  };
  const setLocalWindow = (value: number) => {
    setWindowId(value);
    setTab(current => current === 'all' ? current : 'summary');
    if (group) selectRelation({ model: 'DGraFormer', dataset: String((session.dataset as any).name), sample: graphSample, contextType: 'window', contextIndex: value, source: group.source, target: group.target, sourceName: group.sourceName, targetName: group.targetName });
  };

  return <section id="dgra-session-v2-evidence" className="mx-auto max-w-[1400px] space-y-5 px-5 pb-14">
    <section className="card p-5">
      <div className="eyebrow">Relations to inspect</div>
      <div className="mt-3 flex flex-wrap gap-2">{groups.map(item => <button key={`${item.source}->${item.target}`} onClick={() => choose(item.source, item.target)} className={`rounded-lg border px-4 py-2.5 text-[11px] font-semibold transition ${relationKey === `${item.source}->${item.target}` ? 'border-[#263b59] bg-[#263b59] text-white' : 'border-line bg-white text-ink-700 hover:border-[#263b59]'}`}>{item.sourceName} → {item.targetName}</button>)}</div>
      {!group && <p className="mt-4 rounded-lg bg-[#f5f7fa] p-4 text-[12px] text-ink-500">Select a relation to inspect its functional evidence.</p>}
    </section>
    {group && <>
      {multiple && <section className="card flex flex-wrap items-center gap-3 p-4"><span className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">Local window</span>{group.retained.map(value => <button key={value} onClick={() => setLocalWindow(value)} className={`rounded-md px-3 py-2 text-[10px] font-semibold ${value === windowId ? 'bg-[#16827f] text-white' : 'bg-[#edf1f5] text-ink-600'}`}>W{value}</button>)}<span className="text-[10px] text-ink-400">Deterministic retained-window order; independent of outcomes.</span></section>}
      <EvidenceTabs value={tab} onChange={setTab} tabs={multiple ? [['summary','Evidence Summary'],['single','Single-window Detail'],['all','All-window Detail']] : [['summary','Evidence Summary'],['intervention','Intervention Detail']]}/>
      {tab === 'summary' && <DgraSummary session={session} group={group} local={local} all={all} sampleId={sampleId}/>} 
      {(tab === 'single' || tab === 'intervention') && <CaseDetail session={session} bundle={local ?? all} sampleId={sampleId} setSampleId={setSampleId} scopeNote={multiple ? `W${windowId} only` : 'Single retained window = all retained windows'}/>} 
      {tab === 'all' && <CaseDetail session={session} bundle={all} sampleId={sampleId} setSampleId={setSampleId} scopeNote={`All retained windows: ${group.retained.map(value => `W${value}`).join(', ')}`}/>} 
    </>}
  </section>;
}

export function MsgnetSessionV2Evidence({ supplied }: { supplied?: AuditSessionV2 | null }) {
  const { session, error } = useSession('MSGNet', supplied);
  const selection = useWorkflowStore(state => state.selection);
  const [tab, setTab] = useState<Tab>('summary');
  const [summaryTest, setSummaryTest] = useState<number | null>(null);
  const [testA, setTestA] = useState<number | null>(null);
  const [testB, setTestB] = useState<number | null>(null);
  const selected = selection?.model === 'MSGNet' && selection.contextType === 'scale' ? selection : null;

  useEffect(() => { setTab('summary'); }, [selected?.source, selected?.target, selected?.contextIndex]);
  useEffect(() => {
    if (!session) return;
    const ids = session.samples.map(sample => sample.sample_index);
    setSummaryTest(ids[0] ?? null); setTestA(ids[0] ?? null); setTestB(ids.length ? ids[ids.length - 1] : null);
  }, [session]);

  if (error) return <LoadFailure error={error}/>;
  if (!session) return <Loading label="Loading frozen MSGNet Session v2…"/>;
  if (!selected) return <section id="msgnet-session-v2-evidence" className="mx-auto max-w-[1400px] px-5 pb-14"><div className="card p-5 text-center text-[12px] text-ink-500">Click an edge in the graph to inspect its evidence.</div></section>;

  const single = exactCandidate(session, candidate => candidate.scope === 'single_scale' && candidate.scale_index === selected.contextIndex && candidate.source === selected.source && candidate.target === selected.target);
  const all = exactCandidate(session, candidate => candidate.scope === 'all_scales' && candidate.source === selected.source && candidate.target === selected.target);
  return <section id="msgnet-session-v2-evidence" className="mx-auto max-w-[1400px] space-y-5 px-5 pb-14">
    <EvidenceTabs value={tab} onChange={setTab} tabs={[["summary","Evidence Summary"],["single","Single-scale Detail"],["all","All-scale Detail"]]}/>
    {tab === 'summary' && <MsgnetSummary session={session} single={single} all={all} testId={summaryTest} setTestId={setSummaryTest}/>} 
    {tab === 'single' && <TwoCaseDetail session={session} bundle={single} testA={testA} testB={testB} setTestA={setTestA} setTestB={setTestB} scope="Single scale"/>}
    {tab === 'all' && <TwoCaseDetail session={session} bundle={all} testA={testA} testB={testB} setTestA={setTestA} setTestB={setTestB} scope="All scales"/>}
  </section>;
}

function DgraSummary({ session, group, local, all, sampleId }: { session: AuditSessionV2; group: ReturnType<typeof relationGroups>[number]; local: CandidateBundle | null; all: CandidateBundle | null; sampleId: number | null }) {
  const multiple = group.retained.length > 1;
  if (!all && !local) return <Unavailable text="Formal candidate evidence is unavailable for this exact relation."/>;
  const chartBundle = multiple ? local : all ?? local;
  const chartCase = chartBundle && sampleId !== null ? exactCase(session, chartBundle.candidate, sampleId) : null;
  return <section className="space-y-5">
    <Headline relation={`${group.sourceName} → ${group.targetName}`} supported={Boolean((all ?? local)?.evidence.multiplicity.supported)} available={(all ?? local)?.evidence.primary_inference.status === 'complete'} scope={multiple ? `${group.retained.length} retained windows` : 'One retained window'}/>
    {!multiple && <p className="rounded-lg border border-sky-200 bg-sky-50 p-4 text-[11px] text-sky-900">This relation is retained in only one graph window. Single-window removal and removal across all retained windows therefore represent the same intervention.</p>}
    <div className={`grid gap-5 ${multiple ? 'lg:grid-cols-2' : ''}`}>{multiple && <EvidenceColumn title={`Selected Single Window · W${local?.candidate.window_index ?? '—'}`} bundle={local}/>}<EvidenceColumn title={multiple ? 'All Retained Windows' : 'Relation Removed'} bundle={all ?? local}/></div>
    <TrajectoryPanel session={session} target={group.target} records={[['Relation Removed', chartCase]]} sampleId={sampleId}/>
    <MethodAndProvenance session={session} bundle={all ?? local}/>
  </section>;
}

function MsgnetSummary({ session, single, all, testId, setTestId }: { session: AuditSessionV2; single: CandidateBundle | null; all: CandidateBundle | null; testId: number | null; setTestId: (value: number) => void }) {
  const candidate = single?.candidate ?? all?.candidate;
  if (!candidate) return <Unavailable text="This graph edge is not formally audited for the exact selected scale."/>;
  const singleCase = single && testId !== null ? exactCase(session, single.candidate, testId) : null;
  const allCase = all && testId !== null ? exactCase(session, all.candidate, testId) : null;
  const ids = session.samples.map(sample => sample.sample_index);
  return <section className="space-y-5">
    <Headline relation={`${candidate.source_name} → ${candidate.target_name}`} supported={Boolean(single?.evidence.multiplicity.supported || all?.evidence.multiplicity.supported)} available={single?.evidence.primary_inference.status === 'complete' && all?.evidence.primary_inference.status === 'complete'} scope={`Graph scale: Scale index ${candidate.scale_index}`}/>
    <div className="grid gap-5 lg:grid-cols-2"><EvidenceColumn title={`Single-scale · scale_index ${candidate.scale_index}`} bundle={single}/><EvidenceColumn title="All-scale · scale indices 0, 1, 2" bundle={all}/></div>
    <section className="card p-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">Same-test trajectory comparison</div><p className="mt-1 text-[11px] text-ink-500">The selector changes only this illustrative chart; the frozen 14-test inference is unchanged.</p></div>{testId !== null && <Select value={testId} onChange={setTestId} options={ids.map(value => ({ value, label: `Test ${value}` }))} ariaLabel="Summary test"/>}</div><div className="mt-5"><TrajectoryPanel session={session} target={candidate.target} records={[["Single-scale Removal", singleCase],["All-scale Removal", allCase]]} sampleId={testId} compact/></div></section>
    <MethodAndProvenance session={session} bundle={single}/>
  </section>;
}

function EvidenceColumn({ title, bundle }: { title: string; bundle: CandidateBundle | null }) {
  if (!bundle) return <Unavailable text={`${title}: Unavailable`}/>;
  const { evidence, family } = bundle;
  const effect = evidence.effect;
  const available = evidence.primary_inference.status === 'complete';
  return <article className="card overflow-hidden"><header className="border-b border-line bg-[#fafbfd] px-5 py-4"><div className="text-[10px] font-semibold uppercase tracking-wider text-accent">{title}</div><p className="mt-2 text-[12px] font-semibold text-[#263b59]">{available ? supportText(evidence.multiplicity.supported) : 'Formal inference unavailable'}</p></header><div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-3"><Metric label="Active / planned" value={`${evidence.active_samples.length} / ${evidence.planned_samples.length}`} tip="The relation was exposed and evaluable in this audit unit."/><Metric label="Positive fraction" value={formatProbability(effect.positive_fraction)} tip="Fraction of active audit samples/tests with D > 0."/><Metric label="Mean excess response (D)" value={formatNumber(effect.mean_D)} tip="Average focal intervention response minus the mean response of matched alternative edge interventions."/><Metric label="Median D" value={formatNumber(effect.median_D)}/><Metric label="Primary p" value={available ? formatProbability(evidence.primary_inference.raw_p) : 'Unavailable'}/><Metric label="BH-adjusted q" value={available ? formatProbability(evidence.multiplicity.adjusted_q) : 'Unavailable'} tip="Multiple-testing-adjusted evidence within the predeclared candidate family."/></div><div className="border-t border-line px-5 py-4 text-[10px] text-ink-500">Family {family.family_id} · {family.size} hypotheses · support status read from Session v2</div></article>;
}

function CaseDetail({ session, bundle, sampleId, setSampleId, scopeNote }: { session: AuditSessionV2; bundle: CandidateBundle | null; sampleId: number | null; setSampleId: (value: number) => void; scopeNote: string }) {
  if (!bundle) return <Unavailable text="Exact case evidence is unavailable."/>;
  const ids = bundle.evidence.planned_samples;
  const record = sampleId === null ? null : exactCase(session, bundle.candidate, sampleId);
  return <section className="space-y-5"><CaseSelector label="Frozen audit sample" ids={ids} value={sampleId} onChange={setSampleId}/>{record ? <CaseCard session={session} candidate={bundle.candidate} record={record} scope={scopeNote}/> : <Unavailable text="Unavailable: no exact case matched this sample, context, source, target, and scope."/>}<p className="text-center text-[10px] text-ink-400">Case detail is illustrative inspection. Formal p/q above uses the complete predeclared cross-sample protocol.</p></section>;
}

function TwoCaseDetail({ session, bundle, testA, testB, setTestA, setTestB, scope }: { session: AuditSessionV2; bundle: CandidateBundle | null; testA: number | null; testB: number | null; setTestA: (value: number) => void; setTestB: (value: number) => void; scope: string }) {
  if (!bundle) return <Unavailable text="Exact candidate evidence is unavailable."/>;
  const ids = bundle.evidence.planned_samples;
  const a = testA === null ? null : exactCase(session, bundle.candidate, testA);
  const b = testB === null ? null : exactCase(session, bundle.candidate, testB);
  return <section className="space-y-5"><div className="grid gap-4 sm:grid-cols-2"><CaseSelector label="Test A" ids={ids} value={testA} onChange={setTestA}/><CaseSelector label="Test B" ids={ids} value={testB} onChange={setTestB}/></div><div className="grid gap-5 xl:grid-cols-2">{a ? <CaseCard session={session} candidate={bundle.candidate} record={a} scope={scope}/> : <Unavailable text="Test A unavailable"/>}{b ? <CaseCard session={session} candidate={bundle.candidate} record={b} scope={scope}/> : <Unavailable text="Test B unavailable"/>}</div><p className="text-center text-[10px] text-ink-400">These two real tests are case inspection only. The formal inference uses all {ids.length} frozen tests.</p></section>;
}

function CaseCard({ session, candidate, record, scope }: { session: AuditSessionV2; candidate: CandidateRelation; record: CaseEvidence; scope: string }) {
  const context = record.context as any;
  if (record.status === 'inactive') return <article className="card p-5"><div className="flex items-center gap-2 text-amber-700"><CircleOff size={16}/><h3 className="font-semibold">{candidate.source_name} → {candidate.target_name} · Test {record.sample_id}</h3></div><p className="mt-4 rounded-lg bg-amber-50 p-4 text-[11px] text-amber-900">Not exposed in this sample. No zero value or alternate case was substituted.</p></article>;
  const metrics = record.response_metrics as any;
  const graph = record.graph_effect as any;
  return <article className="card overflow-hidden"><header className="border-b border-line bg-[#fafbfd] px-5 py-4"><div className="eyebrow">{scope}</div><h3 className="mt-1 font-serif text-xl font-semibold text-[#263b59]">{candidate.source_name} → {candidate.target_name} · Test {record.sample_id}</h3>{typeof context.current_period === 'number' && <p className="mt-1 text-[10px] text-ink-400">Scale index {candidate.scale_index} · current FFT period {context.current_period} (case metadata)</p>}</header><div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4"><Metric label="Learned edge weight" value={formatNumber(graph.weight ?? graph.learned_weight ?? graph.learned_edge_weight ?? graph.normalized_weight ?? (Array.isArray(graph.before_weights) ? graph.before_weights[0] : null))}/><Metric label="Structural rank" value={formatNullable(graph.rank ?? record.rank)}/><Metric label="Focal response" value={formatNumber(record.focal_response)}/><Metric label="Unique controls" value={String(record.controls.unique_count)}/><Metric label="Control mean" value={formatNumber(record.controls.mean)}/><Metric label="Control median" value={formatNumber(record.controls.median)}/><Metric label="D" value={formatNumber(record.D)}/><Metric label="Percentile" value={record.percentile === null ? 'Unavailable' : `${record.percentile.toFixed(2)}%`}/><Metric label="Prediction Δ max" value={formatNumber(metrics.prediction_delta_max)}/><Metric label="Δ MAE" value={formatNumber(metrics.error_delta_mae)}/><Metric label="Δ MSE" value={formatNumber(metrics.error_delta_mse)}/></div><div className="border-t border-line p-5"><TrajectoryPanel session={session} target={candidate.target} records={[["Relation Removed", record]]} sampleId={record.sample_id} compact/></div></article>;
}

function TrajectoryPanel({ session, target, records, sampleId, compact = false }: { session: AuditSessionV2; target: number; records: Array<[string, CaseEvidence | null]>; sampleId: number | null; compact?: boolean }) {
  const sample = sampleId === null ? null : sampleById(session, sampleId);
  if (!sample) return <Unavailable text="Trajectory unavailable: exact audit sample was not found."/>;
  const ground = tensorSeries(sample.ground_truth, target);
  const baseline = tensorSeries(sample.baseline_prediction, target);
  const series: Array<[string, number[] | null]> = [['Ground Truth', ground], ['Original Prediction', baseline], ...records.map(([label, record]) => [label, interventionSeries(record, target)] as [string, number[] | null])];
  if (series.some(([, values]) => !values)) return <Unavailable text="Unavailable: the selected same-test trajectory set is incomplete. No fallback was synthesized."/>;
  const length = Math.min(...series.map(([, values]) => values!.length));
  const all = series.flatMap(([, values]) => values!.slice(0, length));
  const min = Math.min(...all), max = Math.max(...all), range = max - min || 1;
  const colors = ['#6b7280','#263b59','#d97706','#16827f'];
  const points = (values: number[]) => values.slice(0, length).map((value, index) => `${(index / Math.max(1, length - 1)) * 100},${94 - ((value - min) / range) * 88}`).join(' ');
  return <div><div className="flex flex-wrap items-center justify-between gap-2"><div className="eyebrow">Prediction comparison · Test {sampleId}</div><div className="flex flex-wrap gap-3">{series.map(([name], index) => <span key={name} className="flex items-center gap-1 text-[9px] text-ink-500"><i className="h-0.5 w-4" style={{ background: colors[index] }}/>{name}</span>)}</div></div><svg viewBox="0 0 100 100" preserveAspectRatio="none" className={`mt-3 w-full rounded-lg border border-line bg-white ${compact ? 'h-44' : 'h-64'}`} role="img" aria-label={`Same-test trajectory comparison for test ${sampleId}`}>{series.map(([name, values], index) => <polyline key={name} fill="none" stroke={colors[index]} strokeWidth={index < 2 ? 1 : 1.25} vectorEffect="non-scaling-stroke" points={points(values!)}/>)}</svg></div>;
}

function MethodAndProvenance({ session, bundle }: { session: AuditSessionV2; bundle: CandidateBundle | null }) {
  if (!bundle) return null;
  const inference = bundle.evidence.primary_inference;
  return <div className="grid gap-5 lg:grid-cols-2"><details className="card p-5"><summary className="cursor-pointer text-[12px] font-semibold text-[#263b59]">Method details & sensitivity</summary><div className="mt-4 space-y-3 text-[10px] leading-relaxed text-ink-500"><p><b>Primary inference:</b> {methodLabel(inference.method)}. One-sided candidate-level inference on mean D; settings are frozen offline.</p><p><b>Dependence:</b> {bundle.dependence?.classification?.split('_').join(' ') ?? 'Unavailable'} · {bundle.dependence?.inference_engine_selected ?? 'Formal inference unavailable'}.</p><div><b>Sensitivity checks (do not replace primary inference):</b><ul className="mt-2 list-disc space-y-1 pl-5">{bundle.evidence.sensitivity.map(item => <li key={item.name}>{sensitivityText(item)}</li>)}</ul></div></div></details><details className="card p-5"><summary className="cursor-pointer text-[12px] font-semibold text-[#263b59]">How evidence is validated & audit provenance</summary><div className="mt-4 space-y-3 text-[10px] leading-relaxed text-ink-500"><p>Learned relation → real graph intervention → unique matched alternatives → per-unit excess response D → cross-unit inference → BH correction → sensitivity inspection.</p><p><b>D</b> = focal intervention response − mean(unique matched-control responses).</p><dl className="grid gap-2 sm:grid-cols-2"><Provenance label="Model" value={String((session.model as any).name)}/><Provenance label="Dataset" value={String((session.dataset as any).name)}/><Provenance label="Checkpoint hash" value={String((session.checkpoint as any).sha256)}/><Provenance label="Config/protocol hash" value={String((session.provenance as any).audit_config_sha256 ?? (session.provenance as any).config_sha256 ?? 'Unavailable')}/><Provenance label="Candidate family" value={bundle.family.family_id}/><Provenance label="Family size" value={String(bundle.family.size)}/></dl></div></details></div>;
}

function EvidenceTabs({ value, onChange, tabs }: { value: Tab; onChange: (value: Tab) => void; tabs: Array<[Tab, string]> }) { return <nav className="card flex flex-wrap gap-2 p-2" aria-label="Evidence views">{tabs.map(([id,label]) => <button key={id} onClick={() => onChange(id)} className={`min-w-[150px] flex-1 rounded-lg px-4 py-3 text-[11px] font-semibold ${value === id ? 'bg-[#263b59] text-white' : 'bg-white text-ink-600 hover:bg-[#f5f7fa]'}`}>{label}</button>)}</nav>; }
function Headline({ relation, supported, available, scope }: { relation: string; supported: boolean; available: boolean; scope: string }) { return <section className="card flex flex-wrap items-center justify-between gap-4 border-l-4 border-l-[#16827f] p-5"><div><div className="eyebrow">{scope}</div><h3 className="mt-1 font-serif text-2xl font-semibold text-[#263b59]">{relation}</h3></div><div className={`flex items-center gap-2 rounded-full px-4 py-2 text-[11px] font-semibold ${!available ? 'bg-slate-100 text-slate-700' : supported ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800'}`}>{!available ? <CircleOff size={14}/> : supported ? <CheckCircle2 size={14}/> : <Info size={14}/>} {!available ? 'Formal inference unavailable' : supportText(supported)}</div></section>; }
function Metric({ label, value, tip }: { label: string; value: string; tip?: string }) { return <div className="rounded-lg bg-[#f5f7fa] p-3" title={tip}><div className="text-[8px] uppercase tracking-wider text-ink-400">{label}</div><div className="mt-1 break-words font-mono text-[11px] font-semibold text-ink-800">{value}</div></div>; }
function Provenance({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-[#f5f7fa] p-3"><dt className="text-[8px] uppercase tracking-wider text-ink-400">{label}</dt><dd className="mt-1 break-all font-mono text-[9px] text-ink-700">{value}</dd></div>; }
function CaseSelector({ label, ids, value, onChange }: { label: string; ids: number[]; value: number | null; onChange: (value: number) => void }) { return <div className="card flex flex-wrap items-center justify-between gap-3 p-4"><div><div className="eyebrow">{label}</div><p className="mt-1 text-[10px] text-ink-400">Frozen protocol order; selection does not alter formal statistics.</p></div>{value !== null && <Select value={value} onChange={onChange} options={ids.map(item => ({ value: item, label: `Test ${item}` }))} ariaLabel={label}/>}</div>; }
function Loading({ label }: { label: string }) { return <div className="mx-auto flex max-w-[1400px] items-center justify-center px-5 py-14 text-[12px] text-ink-400"><LoaderCircle className="mr-2 animate-spin" size={17}/>{label}</div>; }
function LoadFailure({ error }: { error: string }) { return <div className="mx-auto max-w-[1400px] px-5 py-8"><div className="rounded-xl border border-red-200 bg-red-50 p-5 text-[11px] text-red-900"><AlertTriangle size={16}/><b className="ml-2">Formal evidence could not be validated.</b><p className="mt-2">{error}</p></div></div>; }
function Unavailable({ text }: { text: string }) { return <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-[11px] text-amber-900"><CircleOff className="mr-2 inline" size={14}/>{text}</div>; }
function supportText(value: boolean | null) { return value === true ? 'Statistically supported after BH correction' : value === false ? 'No consistent functional evidence was established' : 'Formal inference unavailable'; }
function methodLabel(value: string | null) { if (!value) return 'Formal inference unavailable'; if (value.includes('moving_block')) return 'Dependence-aware moving-block inference'; if (value.includes('exact_sign_flip')) return 'One-sided complete exact sign-flip'; return value.split('_').join(' '); }
function sensitivityText(item: SensitivityResult) { const fact = item.p !== undefined ? `p=${formatProbability(item.p)}` : item.q !== undefined ? `q=${formatProbability(item.q)}` : item.CI !== undefined ? `CI=${JSON.stringify(item.CI)}` : item.value !== undefined ? JSON.stringify(item.value) : formatNullable(item.statistic as any); return `${item.name.split('_').join(' ')}: ${fact}`; }
function tensorSeries(tensor: AuditTensor, target: number): number[] | null { const values = tensor?.values as unknown; if (!Array.isArray(values)) return null; const output = values.map(row => Array.isArray(row) ? row[target] : null); return output.every(value => typeof value === 'number' && Number.isFinite(value)) ? output as number[] : null; }
function interventionSeries(record: CaseEvidence | null, target: number): number[] | null { if (!record || record.status !== 'active') return null; const reference = record.intervention_output_reference as any; const tensor = reference?.value?.values ? reference.value : reference?.values ? reference : null; return tensor ? tensorSeries(tensor, target) : null; }
function formatNumber(value: unknown) { if (typeof value !== 'number' || !Number.isFinite(value)) return 'Unavailable'; const magnitude = Math.abs(value); return magnitude !== 0 && (magnitude < .001 || magnitude >= 1000) ? value.toExponential(4) : value.toFixed(6); }
function formatProbability(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(5) : 'Unavailable'; }
function formatNullable(value: unknown) { return value === null || value === undefined ? 'Unavailable' : String(value); }
