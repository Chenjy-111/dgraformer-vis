import { useEffect, useMemo, useState } from 'react';
import type { AuditSessionV2 } from '@/data/auditSessionV2';
import { exactCandidate, loadBuiltInSessionV2, relationGroups, type CandidateBundle } from '@/data/auditSessionV2View';
import { useDemoStore } from '@/store/useDemoStore';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import {
  EquivalentScopeNotice,
  EvidenceDetail,
  LoadFailure,
  Loading,
  MethodSensitivity,
  ProvenancePanel,
  RelationAuditHeader,
  ScopeEvidenceMap,
  SelectedScopeComparison,
  Unavailable,
  type ScopeMapItem,
} from './evidence/EvidencePresentation';

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

  const groups = useMemo(() => session ? relationGroups(session) : [], [session]);
  const group = groups.find(item => `${item.source}->${item.target}` === relationKey) ?? null;
  const multiple = (group?.retained.length ?? 0) > 1;
  const local = session && group && windowId !== null ? exactCandidate(session, candidate => candidate.source === group.source && candidate.target === group.target && candidate.scope === 'single_window' && candidate.window_index === windowId) : null;
  const all = session && group ? exactCandidate(session, candidate => candidate.source === group.source && candidate.target === group.target && candidate.scope === 'all_retained_windows') : null;
  const localBundles = useMemo(() => session && group ? group.retained.map(context => ({ context, bundle: exactCandidate(session, candidate => candidate.source === group.source && candidate.target === group.target && candidate.scope === 'single_window' && candidate.window_index === context) })) : [], [session, group]);

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
    if (group) selectRelation({ model: 'DGraFormer', dataset: String((session.dataset as any).name), sample: graphSample, contextType: 'window', contextIndex: value, source: group.source, target: group.target, sourceName: group.sourceName, targetName: group.targetName });
  };

  return <section id="dgra-session-v2-evidence" className="mx-auto max-w-[1400px] space-y-5 px-5 pb-14">
    <section className="card p-5"><div className="eyebrow">Relations to inspect</div><div className="mt-3 flex flex-wrap gap-2">{groups.map(item => <button key={`${item.source}->${item.target}`} onClick={() => choose(item.source, item.target)} className={`rounded-lg border px-4 py-2.5 text-[12px] font-semibold transition ${relationKey === `${item.source}->${item.target}` ? 'border-[#263b59] bg-[#263b59] text-white' : 'border-line bg-white text-ink-700 hover:border-[#263b59]'}`}>{item.sourceName} → {item.targetName}</button>)}</div>{!group && <p className="mt-4 rounded-lg bg-[#f5f7fa] p-4 text-[13px] text-ink-500">Select a relation to inspect its functional evidence.</p>}</section>
    {group && <>{multiple && <section className="card flex flex-wrap items-center gap-3 p-4"><span className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Local window</span>{group.retained.map(value => <button key={value} onClick={() => setLocalWindow(value)} className={`rounded-md px-3 py-2 text-[11px] font-semibold ${value === windowId ? 'bg-[#16827f] text-white' : 'bg-[#edf1f5] text-ink-600 hover:bg-[#dfe7ed]'}`}>W{value}</button>)}<span className="text-[11px] text-ink-400">Frozen retained-window order; independent of outcomes.</span></section>}
      <EvidenceTabs value={tab} onChange={setTab} tabs={multiple ? [['summary','Evidence Summary'],['single','Single-window Detail'],['all','All-window Detail']] : [['summary','Evidence Summary'],['intervention','Intervention Detail']]}/>
      {tab === 'summary' && <DgraSummary session={session} group={group} local={local} all={all} localBundles={localBundles} selectedWindow={windowId} onSelectWindow={setLocalWindow}/>}
      {(tab === 'single' || tab === 'intervention') && <EvidenceDetail session={session} bundle={local ?? all} title={multiple ? `Single-window Detail · W${windowId}` : 'Intervention Detail'} scopeNote={multiple ? `W${windowId} only` : 'Single retained window = all retained windows'}/>}
      {tab === 'all' && <EvidenceDetail session={session} bundle={all} title="All-window Detail" scopeNote={`All retained windows: ${group.retained.map(value => `W${value}`).join(', ')}`}/>}
    </>}
  </section>;
}

export function MsgnetSessionV2Evidence({ supplied }: { supplied?: AuditSessionV2 | null }) {
  const { session, error } = useSession('MSGNet', supplied);
  const selection = useWorkflowStore(state => state.selection);
  const selectRelation = useWorkflowStore(state => state.selectRelation);
  const [tab, setTab] = useState<Tab>('summary');
  const selected = selection?.model === 'MSGNet' && selection.contextType === 'scale' ? selection : null;
  const single = session && selected ? exactCandidate(session, candidate => candidate.scope === 'single_scale' && candidate.scale_index === selected.contextIndex && candidate.source === selected.source && candidate.target === selected.target) : null;
  const all = session && selected ? exactCandidate(session, candidate => candidate.scope === 'all_scales' && candidate.source === selected.source && candidate.target === selected.target) : null;
  const scaleBundles = useMemo(() => {
    if (!session || !selected) return [];
    return [...new Set(session.candidate_relations.filter(candidate => candidate.scope === 'single_scale' && candidate.source === selected.source && candidate.target === selected.target && typeof candidate.scale_index === 'number').map(candidate => candidate.scale_index!))].sort((a, b) => a - b).map(context => ({ context, bundle: exactCandidate(session, candidate => candidate.scope === 'single_scale' && candidate.scale_index === context && candidate.source === selected.source && candidate.target === selected.target) }));
  }, [session, selected?.source, selected?.target]);

  useEffect(() => { setTab('summary'); }, [selected?.source, selected?.target, selected?.contextIndex]);
  if (error) return <LoadFailure error={error}/>;
  if (!session) return <Loading label="Loading frozen MSGNet Session v2…"/>;
  if (!selected) return <section id="msgnet-session-v2-evidence" className="mx-auto max-w-[1400px] px-5 pb-14"><div className="card p-5 text-center text-[13px] text-ink-500">Click an edge in the graph to inspect its evidence.</div></section>;

  const setLocalScale = (value: number) => selectRelation({ ...selected, contextIndex: value });
  return <section id="msgnet-session-v2-evidence" className="mx-auto max-w-[1400px] space-y-5 px-5 pb-14">
    <EvidenceTabs value={tab} onChange={setTab} tabs={[["summary","Evidence Summary"],["single","Single-scale Detail"],["all","All-scale Detail"]]}/>
    {tab === 'summary' && <MsgnetSummary session={session} single={single} all={all} scaleBundles={scaleBundles} selectedScale={selected.contextIndex} onSelectScale={setLocalScale}/>}
    {tab === 'single' && <EvidenceDetail session={session} bundle={single} title={`Single-scale Detail · scale_index ${selected.contextIndex}`} scopeNote={`Single scale · scale_index ${selected.contextIndex}`}/>}
    {tab === 'all' && <EvidenceDetail session={session} bundle={all} title="All-scale Detail" scopeNote="All scales"/>}
  </section>;
}

function DgraSummary({ session, group, local, all, localBundles, selectedWindow, onSelectWindow }: { session: AuditSessionV2; group: ReturnType<typeof relationGroups>[number]; local: CandidateBundle | null; all: CandidateBundle | null; localBundles: Array<{ context: number; bundle: CandidateBundle | null }>; selectedWindow: number | null; onSelectWindow: (value: number) => void }) {
  const multiple = group.retained.length > 1;
  const mapItems: ScopeMapItem[] = [...localBundles.map(({ context, bundle }) => ({ key: `window-${context}`, label: `W${context}`, bundle, selected: context === selectedWindow, onSelect: () => onSelectWindow(context) })), { key: 'all-windows', label: 'All retained windows', bundle: all }];
  return <section className="space-y-5"><RelationAuditHeader relation={`${group.sourceName} → ${group.targetName}`} model="DGraFormer" localContext={`W${selectedWindow ?? '—'}`} contextCount={`${group.retained.length} retained window${group.retained.length === 1 ? '' : 's'}`} audited={Boolean(local || all)}/>{!multiple && <EquivalentScopeNotice/>}<SelectedScopeComparison local={local} global={all ?? (!multiple ? local : null)} localLabel={`Selected Single Window · W${selectedWindow ?? '—'}`} globalLabel="All Retained Windows" equivalent={!multiple}/><MethodSensitivity local={local} global={all} localLabel={multiple ? `Local · W${selectedWindow}` : 'Equivalent intervention'} globalLabel="All retained windows"/><ProvenancePanel session={session} bundle={local ?? all}/><ScopeEvidenceMap relation={`${group.sourceName} → ${group.targetName}`} items={mapItems} equivalent={!multiple}/></section>;
}

function MsgnetSummary({ session, single, all, scaleBundles, selectedScale, onSelectScale }: { session: AuditSessionV2; single: CandidateBundle | null; all: CandidateBundle | null; scaleBundles: Array<{ context: number; bundle: CandidateBundle | null }>; selectedScale: number; onSelectScale: (value: number) => void }) {
  const candidate = single?.candidate ?? all?.candidate;
  if (!candidate) return <Unavailable text="This relation is not audited for the exact selected scale or all-scale scope."/>;
  const mapItems: ScopeMapItem[] = [...scaleBundles.map(({ context, bundle }) => ({ key: `scale-${context}`, label: `Scale index ${context}`, bundle, selected: context === selectedScale, onSelect: () => onSelectScale(context) })), { key: 'all-scales', label: 'All scales', bundle: all }];
  return <section className="space-y-5"><RelationAuditHeader relation={`${candidate.source_name} → ${candidate.target_name}`} model="MSGNet" localContext={`scale_index ${selectedScale}`} contextCount={`${scaleBundles.length} scales`} audited={Boolean(single || all)}/><SelectedScopeComparison local={single} global={all} localLabel={`Single-scale · scale_index ${selectedScale}`} globalLabel="All-scale"/><MethodSensitivity local={single} global={all} localLabel={`Single-scale · ${selectedScale}`} globalLabel="All-scale"/><ProvenancePanel session={session} bundle={single ?? all}/><ScopeEvidenceMap relation={`${candidate.source_name} → ${candidate.target_name}`} items={mapItems}/></section>;
}

function EvidenceTabs({ value, onChange, tabs }: { value: Tab; onChange: (value: Tab) => void; tabs: Array<[Tab, string]> }) { return <nav className="card flex flex-wrap gap-2 p-2" aria-label="Evidence views">{tabs.map(([id,label]) => <button key={id} onClick={() => onChange(id)} className={`min-w-[150px] flex-1 rounded-lg px-4 py-3 text-[12px] font-semibold ${value === id ? 'bg-[#263b59] text-white' : 'bg-white text-ink-600 hover:bg-[#f5f7fa]'}`}>{label}</button>)}</nav>; }
