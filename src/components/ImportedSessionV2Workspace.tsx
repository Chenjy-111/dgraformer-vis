import { useEffect, useMemo, useState } from 'react';
import { GraphNetwork } from './charts/GraphNetwork';
import type { GraphEdge } from '@/types/demo';
import type { AuditSessionV2 } from '@/data/auditSessionV2';
import type { AuditTensor } from '@/data/auditSession';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { Select } from './ui/Select';
import { DgraSessionV2Evidence, MsgnetSessionV2Evidence } from './SessionV2Evidence';

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

  useEffect(() => { setContextId(sample?.contexts[0]?.context_id ?? ''); setSelected(null); }, [sampleId, sample]);
  const choose = (edge: GraphEdge) => {
    setSelected({ source: edge.source, target: edge.target });
    selectRelation({ model: String((session.model as any).name), dataset: String((session.dataset as any).name), sample: sample.sample_index, contextType: context.type, contextIndex: context.index, source: edge.source, target: edge.target, sourceName: variables[edge.source] ?? String(edge.source), targetName: variables[edge.target] ?? String(edge.target) });
  };
  const quick = (session.audit_plan as any).audit_mode === 'quick_inspection';
  return <div>
    <div className="mx-auto grid max-w-[1400px] gap-6 px-5 py-12 lg:grid-cols-[270px_1fr_300px]">
      <aside className="card h-fit space-y-4 p-4"><div className="eyebrow">Imported Session v2 graph</div><Select value={sampleId} onChange={setSampleId} options={session.samples.map(item => ({ value: item.sample_index, label: `Test ${item.sample_index}` }))} ariaLabel="Imported v2 sample"/>{sample && <Select value={context.context_id} onChange={value => { setContextId(value); setSelected(null); }} options={sample.contexts.map(item => ({ value: item.context_id, label: `${item.type} ${item.index}` }))} ariaLabel="Imported v2 context"/>}</aside>
      <main className="card min-h-[520px] p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-[15px] font-semibold">Dynamic graph · {context?.type} {context?.index}</h3><p className="mt-1 text-[11px] text-[#176e69]">{(session.model as any).name === 'MSGNet' ? 'Click an edge in the graph to inspect its evidence.' : 'Graph tensors are rendered exactly from the validated imported session.'}</p></div><span className="font-mono text-[10px] text-ink-400">{context?.context_id}</span></div><div className="flex justify-center pt-8"><GraphNetwork variables={variables} edges={edges} layout="circular" showLabels threshold={0} target={0} highlightTarget={false} selectedNode={null} selectedEdge={selected} onClickEdge={choose} size={460}/></div></main>
      <aside className="space-y-4"><Info label="Source">Validated Session v2 · no browser inference</Info><Info label="Graph tensor">{context ? `${preferredGraph(context.graphs)} · ${context.node_count} nodes · ${edges.length} directed edges` : 'Unavailable'}</Info>{selected ? <Info label="Selected relation">{variables[selected.source]} → {variables[selected.target]}</Info> : <Info label="Selection">No relation selected</Info>}{quick && <Info label="Quick Inspection">Cross-sample formal inference was not evaluated for this Quick Inspection.</Info>}</aside>
    </div>
    {(session.model as any).name === 'DGraFormer' ? <DgraSessionV2Evidence supplied={session}/> : (session.model as any).name === 'MSGNet' ? <MsgnetSessionV2Evidence supplied={session}/> : <div className="mx-auto max-w-[1400px] px-5 pb-12"><Info label="Formal inference">{quick ? 'Cross-sample formal inference was not evaluated for this Quick Inspection.' : 'Formal inference unavailable for this model presentation.'}</Info></div>}
  </div>;
}

function preferredGraph(graphs: Record<string, AuditTensor>) { return ['normalized','topk_graph','adaptive','effective','learned_adjacency','transpose_adjacency'].find(name => graphs[name]) ?? Object.keys(graphs)[0]; }
function tensorMatrix(tensor: AuditTensor): number[][] { return Array.isArray(tensor?.values) ? tensor.values as number[][] : []; }
function matrixEdges(matrix: number[][]): GraphEdge[] { return matrix.flatMap((row, source) => row.map((weight, target) => ({ source, target, weight, rank: 0, kept: source !== target && weight > 0 }))).filter(edge => edge.kept).sort((a, b) => b.weight - a.weight || a.source - b.source || a.target - b.target).map((edge, index) => ({ ...edge, rank: index + 1 })); }
function Info({ label, children }: { label: string; children: React.ReactNode }) { return <div className="card p-4"><div className="eyebrow">{label}</div><div className="mt-2 text-[11px] leading-relaxed text-ink-600">{children}</div></div>; }
