import { useMemo, useState } from 'react';
import { ArrowRight, CheckCircle2, CircleOff, Database, FlaskConical, ShieldCheck } from 'lucide-react';
import { GraphMatrix } from './charts/GraphMatrix';
import { GraphNetwork } from './charts/GraphNetwork';
import { Select } from './ui/Select';
import { Slider } from './ui/Slider';
import { findExactEvidence, tensorMatrix, type AuditEvidenceRecord, type AuditRelation, type AuditSession, type GraphContext } from '@/data/auditSession';
import type { GraphEdge } from '@/types/demo';
import { useAuditSessionStore } from '@/store/useAuditSessionStore';
import { useWorkflowStore } from '@/store/useWorkflowStore';

export function ImportedGraphWorkspace() {
  const session = useAuditSessionStore(state => state.session)!;
  const selectWorkflow = useWorkflowStore(state => state.selectRelation);
  const testRelation = useWorkflowStore(state => state.testRelation);
  const [sampleIndex, setSampleIndex] = useState(session.samples[0].sample_index);
  const initialSample = session.samples[0];
  const [contextId, setContextId] = useState(initialSample.contexts[0].context_id);
  const [graphName, setGraphName] = useState(preferredGraph(initialSample.contexts[0]));
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);
  const [topkRatio, setTopkRatio] = useState(.4);
  const [threshold, setThreshold] = useState(0);

  const sample = session.samples.find(item => item.sample_index === sampleIndex) ?? session.samples[0];
  const context = sample.contexts.find(item => item.context_id === contextId) ?? sample.contexts[0];
  const activeGraphName = context.graphs[graphName] ? graphName : preferredGraph(context);
  const matrix = tensorMatrix(context.graphs[activeGraphName]);
  const contextRelations = useMemo(() => session.relations
    .filter(relation => relation.sample_id === sample.sample_id && relation.native_occurrences.some(item => item.context_id === context.context_id))
    .sort((a, b) => relationWeight(b, context.context_id) - relationWeight(a, context.context_id)), [session, sample, context]);
  const selectedRelation = contextRelations.find(item => item.relation_id === selectedRelationId) ?? null;
  const allEdges = useMemo(() => matrixEdges(matrix), [matrix]);
  const displayCount = Math.max(1, Math.ceil(allEdges.length * topkRatio));
  const displayEdges = allEdges.slice(0, displayCount);

  const changeSample = (next: number) => {
    const nextSample = session.samples.find(item => item.sample_index === next) ?? session.samples[0];
    const nextContext = nextSample.contexts[0];
    setSampleIndex(nextSample.sample_index);
    setContextId(nextContext.context_id);
    setGraphName(preferredGraph(nextContext));
    setSelectedRelationId(null);
  };
  const changeContext = (next: string) => {
    const nextContext = sample.contexts.find(item => item.context_id === next) ?? sample.contexts[0];
    setContextId(nextContext.context_id);
    setGraphName(preferredGraph(nextContext));
    setSelectedRelationId(null);
  };
  const chooseRelation = (relation: AuditRelation) => {
    setSelectedRelationId(relation.relation_id);
    selectWorkflow({
      model: session.model.name,
      dataset: session.dataset.name,
      sample: sample.sample_index,
      contextType: context.type,
      contextIndex: context.index,
      source: relation.source,
      target: relation.target,
      sourceName: relation.source_name,
      targetName: relation.target_name,
    });
  };
  const testSelected = () => {
    if (!selectedRelation) return;
    chooseRelation(selectedRelation);
    testRelation();
    setTimeout(() => document.getElementById('validation-workspace')?.scrollIntoView({ behavior: 'smooth' }), 0);
  };

  return <div className="mx-auto max-w-[1400px] px-5 py-8">
    <section className="mb-5 rounded-xl border border-[#16827f]/30 bg-[#edf7f6] p-4">
      <div className="flex items-center gap-2 text-[11px] font-semibold text-[#176e69]"><ShieldCheck size={15}/>Imported Audit Session · validated read-only source</div>
      <p className="mt-2 text-[10px] leading-relaxed text-ink-500">The graph below is loaded from the session. Top-K and threshold affect visibility only; stored graphs, relation identities, interventions, controls, and statistics are unchanged.</p>
    </section>
    <div className="grid gap-5 lg:grid-cols-[280px_1fr_330px]">
      <aside className="card h-fit space-y-5 p-5">
        <div><div className="eyebrow mb-2">Audited sample</div><Select value={sample.sample_index} onChange={changeSample} ariaLabel="Imported session sample" options={session.samples.map(item => ({ value: item.sample_index, label: `test ${item.sample_index}` }))}/></div>
        <div><div className="eyebrow mb-2">Native graph context</div><Select value={context.context_id} onChange={changeContext} ariaLabel="Imported session graph context" options={sample.contexts.map(item => ({ value: item.context_id, label: contextLabel(item) }))}/></div>
        <div><div className="eyebrow mb-2">Stored graph stage</div><Select value={activeGraphName} onChange={setGraphName} ariaLabel="Stored graph stage" options={Object.keys(context.graphs).map(name => ({ value: name, label: humanize(name) }))}/></div>
        <Slider label="Visible Top-K ratio" value={topkRatio} min={.05} max={1} step={.05} onChange={setTopkRatio} format={value => `${Math.round(value * 100)}%`}/>
        <Slider label="Visible weight threshold" value={threshold} min={0} max={1} step={.01} onChange={setThreshold} format={value => value.toFixed(2)}/>
        <div className="rounded-lg bg-[#f5f7fa] p-3 text-[9px] leading-relaxed text-ink-500"><b className="text-ink-700">Display only.</b> Showing {displayEdges.filter(edge => edge.weight >= threshold).length} of {allEdges.length} positive stored edges.</div>
        <NativeMetadata context={context}/>
      </aside>
      <main className="space-y-5">
        <section className="card overflow-hidden"><header className="border-b border-line bg-[#fafbfd] px-5 py-4"><div className="eyebrow">Model-native {context.type} graph</div><h3 className="mt-1 text-[18px] font-semibold">{session.model.name} · {contextLabel(context)}</h3></header><div className="grid place-items-center gap-5 p-5 xl:grid-cols-2"><GraphNetwork variables={session.dataset.variables} edges={displayEdges} layout="circular" showLabels={false} threshold={threshold} target={selectedRelation?.target ?? session.dataset.variables.length - 1} highlightTarget={Boolean(selectedRelation)} selectedNode={null} selectedEdge={selectedRelation ? { source: selectedRelation.source, target: selectedRelation.target } : null} onClickEdge={edge => {const relation = contextRelations.find(item => item.source === edge.source && item.target === edge.target); if (relation) chooseRelation(relation);}} size={330}/><GraphMatrix variables={session.dataset.variables} matrix={matrix} target={selectedRelation?.target} size={360}/></div></section>
        <section className="card p-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">Evidence-bearing relations</div><h3 className="mt-1 text-[17px] font-semibold">Choose an exact stored relation</h3></div><span className="text-[10px] text-ink-400">{contextRelations.length} relations in this context</span></div><div className="mt-4 grid max-h-[320px] gap-2 overflow-y-auto sm:grid-cols-2">{contextRelations.map(relation => <button key={relation.relation_id} onClick={() => chooseRelation(relation)} className={`rounded-lg border p-3 text-left transition ${relation === selectedRelation ? 'border-[#16827f] bg-[#edf7f6]' : 'border-line bg-white hover:border-ink-300'}`}><div className="text-[12px] font-semibold text-[#263b59]">{relation.source_name} <span className="text-accent">→</span> {relation.target_name}</div><div className="mt-1 font-mono text-[9px] text-ink-400">weight {relationWeight(relation, context.context_id).toFixed(6)} · {relation.evidence_ids.length} evidence record(s)</div></button>)}</div></section>
      </main>
      <aside className="card h-fit overflow-hidden lg:sticky lg:top-5"><header className="bg-[#263b59] px-5 py-4 text-white"><div className="text-[9px] uppercase tracking-wider text-white/60">Exact selection</div><h3 className="mt-1 font-serif text-xl font-semibold text-white">{selectedRelation ? `${selectedRelation.source_name} → ${selectedRelation.target_name}` : 'No relation selected'}</h3></header><div className="space-y-3 p-5"><Rail label="Source" value="Imported Audit Session"/><Rail label="Sample" value={`test ${sample.sample_index}`}/><Rail label="Context" value={contextLabel(context)}/><Rail label="Graph stage" value={activeGraphName}/>{selectedRelation ? <><Rail label="Relation ID" value={selectedRelation.relation_id}/><button onClick={testSelected} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-[#263b59] px-4 py-3 text-[11px] font-semibold text-white"><FlaskConical size={14}/>Test this exact relation <ArrowRight size={13}/></button></> : <p className="rounded-lg border border-dashed border-line p-3 text-[10px] text-ink-400">Select an evidence-bearing edge. Visible graph edges without an exact evidence record are not substituted.</p>}</div></aside>
    </div>
  </div>;
}

export function ImportedEvidenceWorkspace() {
  const session = useAuditSessionStore(state => state.session)!;
  const pending = useWorkflowStore(state => state.pendingIntervention);
  if (!pending || pending.model !== session.model.name) return <EmptyEvidence/>;
  const local = findExactEvidence(session, pending, 'local');
  const broader = findExactEvidence(session, pending, 'broader_context');
  const sample = session.samples.find(item => item.sample_index === pending.sample);
  const broaderEmptyMessage = session.model.native_context_type === 'global_graph'
    ? `Not applicable: ${session.model.name} exposes a single global graph, so no broader context exists.`
    : undefined;
  return <div className="mx-auto max-w-[1240px] space-y-5 px-5 py-8">
    <section className="rounded-xl border border-[#16827f]/30 bg-[#edf7f6] p-4"><div className="flex items-center gap-2 text-[11px] font-semibold text-[#176e69]"><Database size={15}/>Stored offline evidence only</div><p className="mt-2 text-[10px] text-ink-500">The browser validates, navigates, filters, and displays this session. It does not run a model, extract a graph, replay an intervention, or recompute p-values.</p></section>
    <section className="card p-5"><div className="eyebrow">Transferred exact selection</div><div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><Rail label="Model / dataset" value={`${pending.model} · ${pending.dataset}`}/><Rail label="Sample" value={`test ${pending.sample}`}/><Rail label="Native context" value={`${pending.contextType} ${pending.contextIndex}`}/><Rail label="Relation" value={`${pending.sourceName} → ${pending.targetName}`}/></div></section>
    <div className="grid gap-5 lg:grid-cols-2"><EvidenceCard title={`Local ${pending.contextType} evidence`} record={local} sample={sample} target={pending.target}/><EvidenceCard title="Broader-context evidence" record={broader} sample={sample} target={pending.target} emptyMessage={broaderEmptyMessage}/></div>
    <section className="card overflow-hidden"><header className="bg-[#263b59] px-5 py-4 text-white"><div className="text-[9px] uppercase tracking-wider text-white/60">Imported provenance</div><h3 className="mt-1 font-serif text-xl font-semibold text-white">Session identity</h3></header><div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4"><Rail label="Adapter" value={session.model.adapter}/><Rail label="Checkpoint hash" value={session.checkpoint.sha256}/><Rail label="Generation run" value={session.provenance.session_generation_run_id}/><Rail label="Validation" value={`${session.provenance.validation.kind} · ${session.provenance.validation.status}`}/></div><p className="border-t border-line px-5 py-3 text-[9px] text-ink-400">Cross-run evidence: {session.cross_run_evidence.status}{session.cross_run_evidence.reason ? ` · ${session.cross_run_evidence.reason}` : ''}</p></section>
  </div>;
}

function EvidenceCard({ title, record, sample, target, emptyMessage }: { title: string; record?: AuditEvidenceRecord; sample?: AuditSession['samples'][number]; target: number; emptyMessage?: string }) {
  if (!record) return <section className="card p-5"><div className="flex items-center gap-2 text-amber-700"><CircleOff size={16}/><h3 className="text-[15px] font-semibold">{title}</h3></div><p className="mt-4 rounded-lg bg-amber-50 p-4 text-[11px] text-amber-800">{emptyMessage ?? 'No evidence available for this exact selection.'}</p></section>;
  if ((record.status === 'missing' || record.status === 'unavailable') && record.value === null) return <section className="card p-5"><div className="flex items-center gap-2 text-amber-700"><CircleOff size={16}/><h3 className="text-[15px] font-semibold">{title}</h3></div><StatusBadge status={record.status}/><p className="mt-4 rounded-lg bg-amber-50 p-4 text-[11px] text-amber-800">{record.reason}</p><ExactKey record={record}/></section>;
  const payload = record.value!;
  return <section className="card overflow-hidden"><header className="border-b border-line bg-[#fafbfd] px-5 py-4"><div className="flex items-center justify-between gap-3"><h3 className="text-[15px] font-semibold">{title}</h3><StatusBadge status={record.status}/></div>{record.reason && <p className="mt-2 text-[10px] text-amber-700">{record.reason}</p>}</header><div className="space-y-5 p-5"><MetricSection label="Stored response metrics" values={payload.metrics}/><MetricSection label="Stored statistics" values={payload.statistics}/><div><div className="eyebrow mb-2">Matched controls</div><div className="grid gap-2 sm:grid-cols-3"><Rail label="Status" value={payload.controls.status}/><Rail label="Count" value={payload.controls.count === null ? '—' : String(payload.controls.count)}/><Rail label="Raw values" value={payload.controls.values.status === 'available' ? `${payload.controls.values.value?.length ?? 0} stored` : payload.controls.values.status}/></div>{payload.controls.values.status === 'available' && <p className="mt-2 break-all rounded-lg bg-[#f5f7fa] p-3 font-mono text-[9px] leading-relaxed text-ink-500">{payload.controls.values.value!.slice(0, 8).map(value => formatValue(value)).join(' · ')}{payload.controls.values.value!.length > 8 ? ' · …' : ''}</p>}</div><StoredOutput payload={payload} sample={sample} target={target}/><ExactKey record={record}/>{payload.limitations.length > 0 && <div><div className="eyebrow mb-2">Limitations</div><ul className="list-disc space-y-1 pl-5 text-[9px] leading-relaxed text-ink-500">{payload.limitations.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul></div>}</div></section>;
}

function StoredOutput({ payload, sample, target }: { payload: NonNullable<AuditEvidenceRecord['value']>; sample?: AuditSession['samples'][number]; target: number }) {
  const output = payload.intervention_output;
  if (output.status !== 'available' || !output.value || !sample) return <div><div className="eyebrow mb-2">Intervention output</div><p className="rounded-lg bg-amber-50 p-3 text-[10px] text-amber-800">{output.status}: {output.reason}</p></div>;
  const baseline = tensorMatrix(sample.baseline_prediction).map(row => row[target]);
  const intervention = tensorMatrix(output.value).map(row => row[target]);
  return <div><div className="eyebrow mb-2">Stored output trajectory · {sample.sample_id} · variable {target}</div><div className="overflow-x-auto"><table className="w-full min-w-[420px] text-left font-mono text-[9px]"><thead className="text-ink-400"><tr><th className="p-2">forecast step</th>{baseline.slice(0, 8).map((_, index) => <th key={index}>{index}</th>)}</tr></thead><tbody><tr className="border-t border-line"><td className="p-2 font-sans font-semibold">baseline</td>{baseline.slice(0, 8).map((value, index) => <td key={index}>{formatValue(value)}</td>)}</tr><tr className="border-t border-line"><td className="p-2 font-sans font-semibold">intervention</td>{intervention.slice(0, 8).map((value, index) => <td key={index}>{formatValue(value)}</td>)}</tr></tbody></table></div><p className="mt-2 text-[9px] text-ink-400">First 8 stored values shown; no response statistic is recomputed in the browser.</p></div>;
}

function ExactKey({ record }: { record: AuditEvidenceRecord }) {
  const item = record.selection;
  return <div><div className="eyebrow mb-2">Exact evidence key</div><p className="break-all rounded-lg bg-[#f5f7fa] p-3 font-mono text-[9px] leading-relaxed text-ink-500">{item.model} · {item.dataset} · {item.sample_id} · {item.context_type}:{String(item.context_index)} · {item.source}→{item.target} · {item.scope}</p></div>;
}

function MetricSection({ label, values }: { label: string; values: Record<string, number | number[] | null> }) {
  const entries = Object.entries(values);
  return <div><div className="eyebrow mb-2">{label}</div>{entries.length ? <div className="grid gap-2 sm:grid-cols-2">{entries.map(([name, value]) => <Rail key={name} label={humanize(name)} value={formatMetric(value)}/>)}</div> : <p className="text-[10px] text-ink-400">No metric stored for this record.</p>}</div>;
}

function NativeMetadata({ context }: { context: GraphContext }) {
  const entries = Object.entries(context.native_metadata).filter(([, value]) => typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean').slice(0, 5);
  return <div><div className="eyebrow mb-2">Native metadata</div><div className="space-y-2">{entries.map(([key, value]) => <Rail key={key} label={humanize(key)} value={String(value)}/>)}</div></div>;
}

function StatusBadge({ status }: { status: string }) {
  const available = status === 'available';
  return <span className={`mt-3 inline-flex items-center gap-1 rounded-full px-2 py-1 text-[9px] font-semibold ${available ? 'bg-emerald-50 text-emerald-700' : status === 'not_exposed' ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}>{available ? <CheckCircle2 size={11}/> : <CircleOff size={11}/>} {humanize(status)}</span>;
}

function EmptyEvidence() {
  return <div className="mx-auto max-w-[1240px] px-5 py-14 text-center text-[12px] text-ink-400">Select an exact relation in the imported graph workspace, then choose “Test this exact relation”.</div>;
}

function Rail({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-[#f5f7fa] p-3"><div className="text-[8px] uppercase tracking-wider text-ink-400">{label}</div><div className="mt-1 break-all text-[10px] font-semibold text-ink-700">{value}</div></div>;
}

function preferredGraph(context: GraphContext) {
  const preferred = context.type === 'window'
    ? ['normalized', 'topk_graph', 'self_loop_graph']
    : context.type === 'global_graph' ? ['learned_adjacency', 'transpose_adjacency'] : ['adaptive', 'effective'];
  return preferred.find(name => context.graphs[name]) ?? Object.keys(context.graphs)[0];
}

function contextLabel(context: GraphContext) {
  if (context.type === 'window') return `window ${context.index}`;
  if (context.type === 'global_graph') return `global learned graph ${context.index}`;
  if (context.type === 'scale') {
    const period = context.native_metadata.period;
    return `layer ${context.layer ?? 0} · scale ${context.index}${typeof period === 'number' ? ` · period ${period}` : ''}`;
  }
  return `${humanize(context.type)} ${context.index}${context.layer === undefined ? '' : ` · layer ${context.layer}`}`;
}

function relationWeight(relation: AuditRelation, contextId: string) {
  return relation.native_occurrences.find(item => item.context_id === contextId)?.weight ?? 0;
}

function matrixEdges(matrix: number[][]): GraphEdge[] {
  const edges: GraphEdge[] = [];
  matrix.forEach((row, source) => row.forEach((weight, target) => {
    if (source !== target && weight > 0) edges.push({ source, target, weight, rank: 0, kept: true });
  }));
  edges.sort((a, b) => b.weight - a.weight || a.source - b.source || a.target - b.target);
  return edges.map((edge, index) => ({ ...edge, rank: index + 1 }));
}

function formatMetric(value: number | number[] | null) {
  if (value === null) return 'null';
  if (Array.isArray(value)) return `[${value.map(formatValue).join(', ')}]`;
  return formatValue(value);
}

function formatValue(value: number) {
  return Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < .0001) ? value.toExponential(4) : value.toFixed(6);
}

function humanize(value: string) {
  return value.split('_').join(' ');
}
