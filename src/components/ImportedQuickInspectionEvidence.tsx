import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, ChevronRight, Database, FlaskConical, ShieldCheck } from 'lucide-react';
import type { AuditSessionV2, AuditTensor, CandidateRelation, CaseEvidence } from '@/data/auditSessionV2';

interface RelationSelection {
  source: number;
  target: number;
}

export function ImportedQuickInspectionEvidence({
  session,
  sampleId,
  contextId,
  selected,
  onSelectRelation,
}: {
  session: AuditSessionV2;
  sampleId: number;
  contextId: string;
  selected: RelationSelection | null;
  onSelectRelation: (candidate: CandidateRelation, record: CaseEvidence) => void;
}) {
  const quick = (session.audit_plan as any).audit_mode === 'quick_inspection';
  const available = useMemo(() => session.candidate_relations.flatMap(candidate => {
    const records = session.case_evidence.filter(record =>
      record.candidate_id === candidate.candidate_id
      && record.sample_id === sampleId
      && String((record.context as any)?.context_id ?? '') === contextId
    );
    return records.map(record => ({ candidate, record }));
  }), [session, sampleId, contextId]);
  const match = selected ? available.find(item => item.candidate.source === selected.source && item.candidate.target === selected.target) ?? null : null;

  return <section id="validation-workspace" className="border-t border-line bg-[#f5f7fa]">
    <div className="mx-auto max-w-[1400px] space-y-5 px-5 py-12">
      <header>
        <div className="eyebrow">Workspace 02</div>
        <h2 className="mt-2 font-serif text-[30px] font-semibold">Intervention Validation</h2>
        <p className="mt-2 max-w-3xl text-[12px] leading-relaxed text-ink-500">Read the checkpoint-replayed edge removal, matched controls and bounded case evidence stored in the imported Session v2. The browser does not rerun the model.</p>
      </header>

      <section className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div><div className="eyebrow">Audited relation stored in this Session</div><p className="mt-2 text-[12px] text-ink-500">The complete learned graph is shown above for context; the highlighted relation is the one selected before this Quick Inspection JSON was generated.</p></div>
          <span className="rounded-full bg-[#edf7f6] px-3 py-1.5 text-[10px] font-semibold text-[#176e69]">{available.length} available for Test {sampleId}</span>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {available.map(({ candidate, record }) => {
            const active = selected?.source === candidate.source && selected?.target === candidate.target;
            return <button key={record.case_evidence_id} type="button" onClick={() => onSelectRelation(candidate, record)} className={`rounded-lg border px-4 py-2.5 text-[12px] font-semibold transition ${active ? 'border-[#263b59] bg-[#263b59] text-white' : 'border-line bg-white text-ink-700 hover:border-[#16827f]'}`}>{candidate.source_name ?? candidate.source} → {candidate.target_name ?? candidate.target}</button>;
          })}
          {available.length === 0 && <p className="rounded-lg bg-amber-50 px-4 py-3 text-[12px] text-amber-900">No case evidence in this Session matches Test {sampleId} and {contextId}.</p>}
        </div>
      </section>

      {!selected && <EmptyEvidence text="Select one of the audited relations above to display its stored intervention evidence."/>}
      {selected && !match && <EmptyEvidence text={`The locked relation ${relationLabel(session, selected.source, selected.target)} has no matching case record for this sample/context. The imported Session may be internally inconsistent.`}/>}
      {match && <QuickCasePresentation session={session} candidate={match.candidate} record={match.record} quick={quick}/>}
    </div>
  </section>;
}

function QuickCasePresentation({ session, candidate, record, quick }: { session: AuditSessionV2; candidate: CandidateRelation; record: CaseEvidence; quick: boolean }) {
  const sample = session.samples.find(item => item.sample_index === record.sample_id) ?? session.samples[0];
  const intervention = interventionTensor(record);
  const controls = record.controls.responses ?? [];
  const metrics = record.response_metrics as Record<string, unknown>;
  const graph = record.graph_effect as Record<string, unknown>;
  const relation = `${candidate.source_name ?? candidate.source} → ${candidate.target_name ?? candidate.target}`;
  const conclusion = boundedConclusion(record);

  if (record.status === 'inactive') return <section className="card p-6"><div className="flex items-center gap-2 text-amber-800"><AlertTriangle size={17}/><h3 className="font-semibold">{relation} is inactive for Test {record.sample_id}</h3></div><p className="mt-3 text-[12px] text-amber-900">No effect value was substituted. This Session records the relation as unavailable for this exact case.</p></section>;

  return <div className="space-y-5">
    <section className="card overflow-hidden border-l-4 border-l-[#16827f]">
      <div className="grid gap-5 p-6 lg:grid-cols-[1fr_auto]">
        <div><div className="flex items-center gap-2 text-[#176e69]"><FlaskConical size={16}/><span className="text-[11px] font-semibold uppercase tracking-wider">Stored structural-edge-removal replay</span></div><h3 className="mt-2 font-serif text-[26px] font-semibold text-[#263b59]">{relation}</h3><p className="mt-2 text-[12px] text-ink-500">Test {record.sample_id} · {String((record.context as any)?.context_id ?? candidate.native_context_type)} · {candidate.scope}</p></div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[11px] leading-relaxed text-amber-900"><b>{quick ? 'Quick Inspection' : 'Case evidence'}</b><br/>Formal p/q inference: not evaluated</div>
      </div>
      <div className="border-t border-line bg-[#fafbfd] p-5"><div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 shrink-0 text-[#16827f]" size={17}/><div><div className="text-[12px] font-semibold text-[#263b59]">Bounded interpretation</div><p className="mt-1 text-[12px] leading-relaxed text-ink-600">{conclusion}</p></div></div></div>
    </section>

    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Metric label="Focal response" value={formatNumber(record.focal_response)} note="Mean absolute prediction change after removing the selected edge" tone="accent"/>
      <Metric label="Control mean" value={formatNumber(record.controls.mean)} note={`${record.controls.unique_count} unique eligible edge removals`}/>
      <Metric label="D = focal − control mean" value={formatSigned(record.D)} note="Descriptive case contrast; not a p-value" tone={Number(record.D) > 0 ? 'positive' : 'negative'}/>
      <Metric label="Control percentile" value={record.percentile === null ? 'Unavailable' : `${record.percentile.toFixed(2)}%`} note={record.rank === null ? 'Rank unavailable' : `Response rank ${record.rank} of ${record.controls.unique_count + 1}`}/>
    </section>

    <section className="card p-5">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">Prediction replay</div><h3 className="mt-1 text-[17px] font-semibold text-[#263b59]">Baseline vs edge-removed forecast</h3><p className="mt-2 text-[11px] text-ink-500">Values are read directly from the validated Session; no browser-side model execution.</p></div><span className="font-mono text-[10px] text-ink-400">metric · prediction_delta_abs</span></div>
      {intervention ? <PredictionReplayChart variables={(session.dataset as any).variables ?? []} target={candidate.target} baseline={sample.baseline_prediction} intervention={intervention} truth={sample.ground_truth}/> : <p className="mt-5 rounded-lg bg-amber-50 p-4 text-[12px] text-amber-900">Intervention prediction tensor is unavailable in this Session.</p>}
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><SmallMetric label="Prediction Δ mean" value={formatNumber(metrics.prediction_delta_abs)}/><SmallMetric label="Prediction Δ max" value={formatNumber(metrics.prediction_delta_max)}/><SmallMetric label="Baseline MAE" value={formatNumber(metrics.baseline_mae)}/><SmallMetric label="Intervention MAE" value={formatNumber(metrics.intervention_mae)}/></div>
    </section>

    <section className="card p-5">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><div className="eyebrow">Matched controls</div><h3 className="mt-1 text-[17px] font-semibold text-[#263b59]">Is the selected edge unusual relative to other removals?</h3><p className="mt-2 text-[11px] text-ink-500">Every dot is one distinct eligible edge removal replay stored offline.</p></div><span className="font-mono text-[10px] text-ink-400">n = {record.controls.unique_count}</span></div>
      {controls.length > 0 ? <ControlResponsePlot responses={controls} focal={Number(record.focal_response)} mean={Number(record.controls.mean)}/> : <p className="mt-5 rounded-lg bg-amber-50 p-4 text-[12px] text-amber-900">Individual control responses were not embedded; summary values remain available.</p>}
      {controls.length > 0 && <details className="mt-4 border-t border-line pt-4"><summary className="cursor-pointer text-[11px] font-semibold text-ink-600">Show all control identities and responses</summary><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{controls.map((value, index) => <div key={`${record.controls.identities[index]}-${index}`} className="flex items-center justify-between rounded-lg bg-[#f5f7fa] px-3 py-2 text-[10px]"><span className="font-mono text-ink-500">{controlLabel(session, record.controls.identities[index])}</span><span className="font-mono font-semibold text-ink-700">{formatNumber(value)}</span></div>)}</div></details>}
    </section>

    <section className="grid gap-5 lg:grid-cols-2">
      <section className="card p-5"><div className="eyebrow">Graph intervention</div><h3 className="mt-1 text-[16px] font-semibold">What changed in the model input?</h3><dl className="mt-4 grid gap-3 sm:grid-cols-2"><Fact label="Native edge weight" value={formatNumber(graph.native_weight ?? graph.weight)}/><Fact label="Stored weight rank" value={formatNullable(graph.weight_rank ?? graph.rank)}/><Fact label="Retained edge count" value={formatNullable(graph.edge_count)}/><Fact label="Model graph context" value={String((record.context as any)?.context_id ?? candidate.native_context_type)}/></dl>{typeof graph.construction === 'string' && graph.construction.length > 0 && <p className="mt-4 rounded-lg bg-[#edf7f6] p-3 text-[11px] leading-relaxed text-[#176e69]">{graph.construction}</p>}</section>
      <section className="card p-5"><div className="flex items-center gap-2"><ShieldCheck size={16} className="text-[#16827f]"/><div className="eyebrow">Provenance</div></div><h3 className="mt-1 text-[16px] font-semibold">Which artifacts produced this result?</h3><dl className="mt-4 space-y-3"><Fact label="Adapter" value={`${String((session.model as any).adapter)} · ${String((session.model as any).adapter_id)}`}/><Fact label="Dataset SHA-256" value={String((session.dataset as any).sha256 ?? 'Unavailable')}/><Fact label="Checkpoint SHA-256" value={String((session.checkpoint as any).sha256 ?? 'Unavailable')}/><Fact label="Config SHA-256" value={String((session.provenance as any).config_sha256 ?? 'Unavailable')}/></dl></section>
    </section>

    <details className="card p-5"><summary className="cursor-pointer list-none"><div className="flex items-center justify-between"><div><div className="eyebrow">Interpretation boundary</div><p className="mt-2 text-[12px] text-ink-500">What this imported Quick Inspection can and cannot establish</p></div><ChevronRight size={17} className="text-ink-400"/></div></summary><div className="mt-5 grid gap-4 border-t border-line pt-5 lg:grid-cols-2"><Boundary title="Supported presentation" items={['A real checkpoint-backed baseline prediction is stored.','The selected learned edge was structurally removed and the model was replayed offline.','The focal response is compared with unique eligible control removals.']}/><Boundary title="Not established" items={['No case-level p-value or BH-adjusted q-value is computed.','A positive D does not by itself establish statistical support.','The browser does not rerun the model or infer missing evidence.']}/></div></details>
  </div>;
}

function PredictionReplayChart({ variables, target, baseline, intervention, truth }: { variables: string[]; target: number; baseline: AuditTensor; intervention: AuditTensor; truth: AuditTensor }) {
  const base = tensorForecastMatrix(baseline);
  const changed = tensorForecastMatrix(intervention);
  const actual = tensorForecastMatrix(truth);
  const steps = Math.min(base.length, changed.length, actual.length);
  const variableCount = Math.min(base[0]?.length ?? 0, changed[0]?.length ?? 0, actual[0]?.length ?? 0);
  const [variable, setVariable] = useState(Math.min(target, Math.max(variableCount - 1, 0)));
  useEffect(() => { setVariable(Math.min(target, Math.max(variableCount - 1, 0))); }, [target, variableCount]);
  const singleStep = steps === 1;
  const labels = singleStep ? Array.from({ length: variableCount }, (_, index) => variables[index] ?? `V${index}`) : Array.from({ length: steps }, (_, index) => `+${index + 1}`);
  const series = singleStep
    ? [{ label: 'Ground truth', color: '#2c5bd6', values: actual[0] ?? [] }, { label: 'Baseline', color: '#7b8797', values: base[0] ?? [] }, { label: 'Edge removed', color: '#d3543c', values: changed[0] ?? [] }]
    : [{ label: 'Ground truth', color: '#2c5bd6', values: actual.map(row => row[variable]) }, { label: 'Baseline', color: '#7b8797', values: base.map(row => row[variable]) }, { label: 'Edge removed', color: '#d3543c', values: changed.map(row => row[variable]) }];
  if (!steps || !variableCount) return <p className="mt-5 rounded-lg bg-amber-50 p-4 text-[12px] text-amber-900">Prediction tensors could not be mapped to forecast-step × variable axes.</p>;
  const deltaValues = singleStep ? (base[0] ?? []).map((value, index) => Math.abs(value - (changed[0]?.[index] ?? value))) : base.map((row, index) => Math.abs(row[variable] - (changed[index]?.[variable] ?? row[variable])));
  return <div className="mt-5">{!singleStep && <label className="mb-3 flex items-center gap-3 text-[11px] font-semibold text-ink-600">Output variable<select value={variable} onChange={event => setVariable(Number(event.target.value))} className="rounded-lg border border-line bg-white px-3 py-2">{Array.from({ length: variableCount }, (_, index) => <option key={index} value={index}>{variables[index] ?? `V${index}`}</option>)}</select></label>}<LineComparison labels={labels} series={series}/><div className="mt-3 flex flex-wrap gap-4">{series.map(item => <span key={item.label} className="inline-flex items-center gap-2 text-[10px] text-ink-500"><span className="h-0.5 w-5" style={{ backgroundColor: item.color }}/>{item.label}</span>)}</div><p className="mt-2 text-[10px] text-ink-400">{singleStep ? 'One-step forecast vector shown across output variables.' : `Forecast trajectory for ${variables[variable] ?? `V${variable}`}.`}</p><DeltaBars labels={labels} values={deltaValues}/></div>;
}

function DeltaBars({ labels, values }: { labels: string[]; values: number[] }) {
  const maximum = Math.max(...values, Number.EPSILON);
  return <section className="mt-6 rounded-xl border border-line bg-[#fafbfd] p-4"><div className="text-[11px] font-semibold text-[#263b59]">Magnified absolute prediction change</div><p className="mt-1 text-[10px] text-ink-400">Independent scale for |baseline − edge removed|; use the printed values, not bar length, for exact comparison.</p><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{values.map((value, index) => <div key={`${labels[index]}-${index}`} className="rounded-lg bg-white p-3"><div className="flex items-center justify-between gap-2 text-[10px]"><span className="font-semibold text-ink-600">{labels[index]}</span><span className="font-mono text-[#b63e2b]">{formatNumber(value)}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-[#eef1f5]"><div className="h-full rounded-full bg-[#d3543c]" style={{ width: `${Math.max(2, value / maximum * 100)}%` }}/></div></div>)}</div></section>;
}

function LineComparison({ labels, series }: { labels: string[]; series: Array<{ label: string; color: string; values: number[] }> }) {
  const width = 960, height = 280, left = 62, right = 24, top = 20, bottom = 48;
  const values = series.flatMap(item => item.values).filter(Number.isFinite);
  let min = Math.min(...values), max = Math.max(...values);
  if (min === max) { min -= 1; max += 1; }
  const margin = (max - min) * .08;
  min -= margin; max += margin;
  const x = (index: number) => labels.length === 1 ? (left + width - right) / 2 : left + index * (width - left - right) / (labels.length - 1);
  const y = (value: number) => top + (max - value) * (height - top - bottom) / (max - min);
  const ticks = Array.from({ length: 5 }, (_, index) => min + index * (max - min) / 4);
  return <svg viewBox={`0 0 ${width} ${height}`} className="w-full overflow-visible" role="img" aria-label="Ground truth, baseline and edge-removed prediction comparison">{ticks.map(value => <g key={value}><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} stroke="#e5e9ef"/><text x={left - 8} y={y(value) + 3} textAnchor="end" fontSize="9" fill="#7b8797">{compactNumber(value)}</text></g>)}{series.map(item => <g key={item.label}><polyline points={item.values.map((value, index) => `${x(index)},${y(value)}`).join(' ')} fill="none" stroke={item.color} strokeWidth="2.4" strokeLinejoin="round"/>{item.values.map((value, index) => <circle key={index} cx={x(index)} cy={y(value)} r="3.5" fill={item.color}><title>{`${item.label} · ${labels[index]}: ${value}`}</title></circle>)}</g>)}{labels.map((label, index) => <text key={label} x={x(index)} y={height - 18} textAnchor="middle" fontSize="9" fill="#657285">{label}</text>)}</svg>;
}

function ControlResponsePlot({ responses, focal, mean }: { responses: number[]; focal: number; mean: number }) {
  const width = 960, height = 170, left = 45, right = 25, top = 28, bottom = 40;
  let min = Math.min(...responses, focal, mean), max = Math.max(...responses, focal, mean);
  if (min === max) { min -= 1; max += 1; }
  const margin = (max - min) * .08; min -= margin; max += margin;
  const x = (value: number) => left + (value - min) * (width - left - right) / (max - min);
  const ticks = Array.from({ length: 5 }, (_, index) => min + index * (max - min) / 4);
  return <div className="mt-5"><svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Focal response compared with matched control responses"><line x1={left} x2={width - right} y1={height - bottom} y2={height - bottom} stroke="#8d98a8"/>{ticks.map(value => <g key={value}><line x1={x(value)} x2={x(value)} y1={height - bottom} y2={height - bottom + 5} stroke="#8d98a8"/><text x={x(value)} y={height - 17} textAnchor="middle" fontSize="9" fill="#657285">{compactNumber(value)}</text></g>)}{responses.map((value, index) => <circle key={index} cx={x(value)} cy={height - bottom - 14 - (index % 4) * 15} r="5" fill="#9aa5b3" opacity=".72"><title>{`Control ${index + 1}: ${value}`}</title></circle>)}<line x1={x(mean)} x2={x(mean)} y1={top} y2={height - bottom} stroke="#16827f" strokeWidth="2" strokeDasharray="5 4"/><text x={x(mean)} y={top - 8} textAnchor="middle" fontSize="10" fill="#176e69">control mean</text><line x1={x(focal)} x2={x(focal)} y1={top} y2={height - bottom} stroke="#d3543c" strokeWidth="3"/><text x={x(focal)} y={height - bottom + 18} textAnchor="middle" fontSize="10" fontWeight="700" fill="#b63e2b">focal</text></svg><div className="flex flex-wrap gap-4 text-[10px] text-ink-500"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#9aa5b3]"/>Control removal</span><span className="inline-flex items-center gap-2"><span className="h-3 w-0.5 bg-[#d3543c]"/>Selected-edge removal</span><span className="inline-flex items-center gap-2"><span className="h-3 w-0.5 bg-[#16827f]"/>Control mean</span></div></div>;
}

function tensorForecastMatrix(tensor: AuditTensor): number[][] {
  if (!tensor || !Array.isArray(tensor.shape) || !Array.isArray(tensor.axis_order)) return [];
  const shape = tensor.shape;
  let stepAxis = tensor.axis_order.indexOf('forecast_step');
  let variableAxis = tensor.axis_order.indexOf('variable');
  if (variableAxis < 0) variableAxis = shape.length - 1;
  if (stepAxis < 0) stepAxis = shape.length > 1 ? shape.length - 2 : 0;
  const steps = shape[stepAxis] ?? 0, variables = shape[variableAxis] ?? 0;
  const at = (indices: number[]) => {
    let cursor: unknown = tensor.values;
    for (const index of indices) cursor = Array.isArray(cursor) ? cursor[index] : undefined;
    return typeof cursor === 'number' && Number.isFinite(cursor) ? cursor : Number.NaN;
  };
  return Array.from({ length: steps }, (_, step) => Array.from({ length: variables }, (_, variable) => {
    const indices = Array(shape.length).fill(0);
    indices[stepAxis] = step; indices[variableAxis] = variable;
    return at(indices);
  }));
}

function interventionTensor(record: CaseEvidence): AuditTensor | null {
  const reference = record.intervention_output_reference as any;
  const value = reference?.value ?? reference;
  return value && Array.isArray(value.shape) && Array.isArray(value.values) ? value as AuditTensor : null;
}

function boundedConclusion(record: CaseEvidence) {
  if (record.D === null || record.focal_response === null || record.controls.mean === null) return 'The case does not contain a complete focal-versus-control contrast.';
  if (record.D > 0) return `Removing this edge changed the prediction more than the average matched control removal for this case (D = ${formatSigned(record.D)}). This is descriptive Quick Inspection evidence, not formal statistical support.`;
  if (record.D < 0) return `Removing this edge changed the prediction less than the average matched control removal for this case (D = ${formatSigned(record.D)}). This case does not show an unusually large effect relative to its controls.`;
  return 'The selected-edge response equals the matched-control mean for this case (D = 0). No formal statistical conclusion is available.';
}

function relationLabel(session: AuditSessionV2, source: number, target: number) { const variables = (session.dataset as any).variables ?? []; return `${variables[source] ?? source} → ${variables[target] ?? target}`; }
function controlLabel(session: AuditSessionV2, identity: string) { const [source, target] = identity.split('->').map(Number); return Number.isInteger(source) && Number.isInteger(target) ? relationLabel(session, source, target) : identity; }
function formatNumber(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(6) : 'Unavailable'; }
function compactNumber(value: number) { return Math.abs(value) >= .01 ? value.toFixed(3) : value.toExponential(2); }
function formatSigned(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? `${value > 0 ? '+' : ''}${value.toPrecision(6)}` : 'Unavailable'; }
function formatNullable(value: unknown) { return value === null || value === undefined ? 'Unavailable' : String(value); }

function Metric({ label, value, note, tone = 'neutral' }: { label: string; value: string; note: string; tone?: 'neutral' | 'accent' | 'positive' | 'negative' }) { const color = tone === 'accent' ? 'text-[#176e69]' : tone === 'positive' ? 'text-emerald-700' : tone === 'negative' ? 'text-amber-700' : 'text-[#263b59]'; return <article className="card p-5"><div className="eyebrow">{label}</div><div className={`mt-3 font-mono text-[22px] font-semibold ${color}`}>{value}</div><p className="mt-2 text-[10px] leading-relaxed text-ink-400">{note}</p></article>; }
function SmallMetric({ label, value }: { label: string; value: string }) { return <div className="rounded-lg bg-[#f5f7fa] p-3"><div className="text-[9px] font-semibold uppercase tracking-wider text-ink-400">{label}</div><div className="mt-1 font-mono text-[12px] font-semibold text-ink-700">{value}</div></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="min-w-0"><dt className="text-[9px] font-semibold uppercase tracking-wider text-ink-400">{label}</dt><dd className="mt-1 break-all font-mono text-[10px] font-semibold text-ink-700">{value}</dd></div>; }
function Boundary({ title, items }: { title: string; items: string[] }) { return <section><h4 className="text-[13px] font-semibold text-[#263b59]">{title}</h4><ul className="mt-3 space-y-2 text-[11px] leading-relaxed text-ink-500">{items.map(item => <li key={item}>• {item}</li>)}</ul></section>; }
function EmptyEvidence({ text }: { text: string }) { return <section className="card border-dashed p-6 text-center"><Database className="mx-auto text-ink-300" size={25}/><p className="mx-auto mt-3 max-w-2xl text-[12px] leading-relaxed text-ink-500">{text}</p></section>; }
