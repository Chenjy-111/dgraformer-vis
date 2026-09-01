import { useEffect, useMemo, useState } from 'react';
import { GraphNetwork } from './charts/GraphNetwork';
import type { GraphEdge } from '@/types/demo';
import type { AuditSessionV2, AuditTensor, CandidateRelation, CaseEvidence } from '@/data/auditSessionV2';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { Select } from './ui/Select';
import { DgraSessionV2Evidence, MsgnetSessionV2Evidence } from './SessionV2Evidence';
import { ImportedQuickInspectionEvidence } from './ImportedQuickInspectionEvidence';

export function ImportedSessionV2Workspace({ session }: { session: AuditSessionV2 }) {
  const selectRelation = useWorkflowStore(state => state.selectRelation);
  const [sampleId, setSampleId] = useState(session.samples[0]?.sample_index ?? 0);
  const sample = session.samples.find(item => item.sample_index === sampleId) ?? session.samples[0];
  const [contextId, setContextId] = useState(sample?.contexts[0]?.context_id ?? '');
  const context = sample?.contexts.find(item => item.context_id === contextId) ?? sample?.contexts[0];
  const variables = (session.dataset as any).variables as string[];
  const matrix = context ? tensorMatrix(context.graphs[preferredGraph(context.graphs)]) : [];
  const edges = useMemo(() => matrixEdges(matrix), [matrix]);
  const [selected, setSelected] = useState<{ source: number; target: number } | null>(null);

  const available = useMemo(() => session.candidate_relations.flatMap(candidate => session.case_evidence
    .filter(record => record.candidate_id === candidate.candidate_id && record.sample_id === sampleId && String((record.context as any)?.context_id ?? '') === String(context?.context_id ?? ''))
    .map(record => ({ candidate, record }))), [session, sampleId, context?.context_id]);
  const chooseAudited = (candidate: CandidateRelation, record: CaseEvidence) => {
    setSelected({ source: candidate.source, target: candidate.target });
    selectRelation({ model: String((session.model as any).name), dataset: String((session.dataset as any).name), sample: record.sample_id, contextType: String((record.context as any)?.type ?? context.type), contextIndex: Number((record.context as any)?.context_index ?? context.index), source: candidate.source, target: candidate.target, sourceName: candidate.source_name ?? variables[candidate.source] ?? String(candidate.source), targetName: candidate.target_name ?? variables[candidate.target] ?? String(candidate.target) });
  };
  useEffect(() => { setContextId(sample?.contexts[0]?.context_id ?? ''); }, [sampleId, sample]);
  useEffect(() => {
    if (available.length > 0) chooseAudited(available[0].candidate, available[0].record);
    else setSelected(null);
  }, [sampleId, context?.context_id, session]);
  const quick = (session.audit_plan as any).audit_mode === 'quick_inspection';
  const specializedContext = ['window', 'scale', 'global_graph'].includes(String(context?.type));
  return <div>
    <div className="mx-auto grid max-w-[1400px] gap-6 px-5 py-12 lg:grid-cols-[270px_1fr_300px]">
      <aside className="card h-fit space-y-4 p-4"><div className="eyebrow">Imported Session v2 graph</div><Select value={sampleId} onChange={setSampleId} options={session.samples.map(item => ({ value: item.sample_index, label: `Test ${item.sample_index}` }))} ariaLabel="Imported v2 sample"/>{sample && <Select value={context.context_id} onChange={value => setContextId(value)} options={sample.contexts.map(item => ({ value: item.context_id, label: `${item.type} ${item.index}` }))} ariaLabel="Imported v2 context"/>}<p className="rounded-lg bg-[#f5f7fa] p-3 text-[10px] leading-relaxed text-ink-500">The full learned graph is shown as context. The blue edge is the relation whose removal was actually replayed offline.</p></aside>
      <main className="card min-h-[520px] p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-[15px] font-semibold">Learned graph · {context?.type} {context?.index}</h3><p className="mt-1 text-[11px] text-[#176e69]">Stored graph tensor with the audited relation fixed by the imported Session.</p></div><span className="font-mono text-[10px] text-ink-400">{context?.context_id}</span></div><div className="flex justify-center pt-8"><GraphNetwork variables={variables} edges={edges} layout="circular" showLabels threshold={0} target={selected?.target ?? 0} highlightTarget={selected !== null} selectedNode={null} selectedEdge={selected} size={460}/></div></main>
      <aside className="space-y-4"><Info label="Source">Validated Session v2 · no browser inference</Info><Info label="Graph tensor">{context ? `${preferredGraph(context.graphs)} · ${context.node_count} nodes · ${edges.length} directed edges` : 'Unavailable'}</Info>{!specializedContext && <Info label="Generic graph context">Context type “{context?.type}” is preserved from Session v2 and rendered generically; no window/scale semantics are inferred.</Info>}{selected ? <Info label="Audited relation · locked">{variables[selected.source]} → {variables[selected.target]}</Info> : <Info label="Audited relation">No stored case evidence for this context</Info>}{quick && <Info label="Quick Inspection">One selected-edge removal plus {session.case_evidence.find(item => item.sample_id === sampleId)?.controls.unique_count ?? 0} matched controls are stored in this JSON.</Info>}</aside>
    </div>
    {quick ? <ImportedQuickInspectionEvidence session={session} sampleId={sampleId} contextId={String(context?.context_id ?? '')} selected={selected} onSelectRelation={chooseAudited}/> : (session.model as any).name === 'DGraFormer' ? <DgraSessionV2Evidence supplied={session}/> : (session.model as any).name === 'MSGNet' ? <MsgnetSessionV2Evidence supplied={session}/> : <div className="mx-auto max-w-[1400px] px-5 pb-12"><Info label="Formal inference">Formal inference unavailable for this model presentation.</Info></div>}
  </div>;
}

function preferredGraph(graphs: Record<string, AuditTensor>) { return ['normalized','topk_graph','adaptive','effective','learned_adjacency','audit_graph','transpose_adjacency'].find(name => graphs[name]) ?? Object.keys(graphs)[0]; }
function tensorMatrix(tensor: AuditTensor): number[][] { return Array.isArray(tensor?.values) ? tensor.values as number[][] : []; }
function matrixEdges(matrix: number[][]): GraphEdge[] { return matrix.flatMap((row, source) => row.map((weight, target) => ({ source, target, weight, rank: 0, kept: source !== target && weight > 0 }))).filter(edge => edge.kept).sort((a, b) => b.weight - a.weight || a.source - b.source || a.target - b.target).map((edge, index) => ({ ...edge, rank: index + 1 })); }
function Info({ label, children }: { label: string; children: React.ReactNode }) { return <div className="card p-4"><div className="eyebrow">{label}</div><div className="mt-2 text-[11px] leading-relaxed text-ink-600">{children}</div></div>; }
