import { useEffect } from 'react';
import { ChevronLeft, ChevronRight, GitBranch, LockKeyhole, Waves } from 'lucide-react';
import { Hero } from './components/Hero';
import { ResearchMotivation } from './components/ResearchMotivation';
import { MethodExplainer } from './components/MethodExplainer';
import { SystemOverview } from './components/SystemOverview';
import { SystemArchitecture } from './components/SystemArchitecture';
import { CaseStudy } from './components/CaseStudy';
import { Limitations } from './components/Limitations';
import { CitationSection } from './components/CitationSection';
import { VisualizationCanvas } from './components/VisualizationCanvas';
import { ControlStudio } from './components/ControlStudio';
import { ExplanationInspector } from './components/ExplanationInspector';
import { CombinedInterventionLab } from './components/CombinedInterventionLab';
import { MsgnetDataWorkspace, MsgnetDiagnosticWorkspace } from './components/MsgnetWorkspace';
import { InterventionErrorBoundary } from './components/InterventionErrorBoundary';
import { DgraSelectionBridge, TransferBanner, WorkflowBar } from './components/WorkflowChrome';
import { AuditSessionImport } from './components/AuditSessionImport';
import { ImportedEvidenceWorkspace, ImportedGraphWorkspace } from './components/ImportedAuditWorkspace';
import { useDemoStore } from './store/useDemoStore';
import { useWorkflowStore, type WorkflowModel } from './store/useWorkflowStore';
import { useAuditSessionStore } from './store/useAuditSessionStore';

export default function App() {
  const model = useWorkflowStore(state => state.model);
  const setModel = useWorkflowStore(state => state.setModel);
  const pending = useWorkflowStore(state => state.pendingIntervention);
  const load = useDemoStore(state => state.loadCurrent);
  const immersive = useDemoStore(state => state.view === 'graph' && state.graphLayout === '3d-timeline');
  const collapsed = useDemoStore(state => state.inspectorCollapsed);
  const setDemo = useDemoStore(state => state.set);
  const source = useAuditSessionStore(state => state.source);
  const session = useAuditSessionStore(state => state.session);
  const imported = source === 'imported' && session !== null;

  useEffect(() => { void load(); }, [load]);

  return <div className="min-h-screen bg-paper">
    <Hero/>
    <AuditSessionImport/>
    <ResearchMotivation/>
    <MethodExplainer/>
    <SystemOverview/>
    <WorkflowBar/>
    <section id="discovery-workspace" className="border-b border-line bg-white">
      <WorkspaceHeader number="01" title="Pattern Discovery" text={imported ? 'Inspect stored model-native graphs and select an exact imported relation.' : 'Find a learned relation worth testing.'}/>
      {imported ? <ImportedModelLock model={session.model.name} context={session.model.native_context_type}/> : <ModelSwitch value={model} onChange={setModel}/>}
      {imported
        ? <ImportedGraphWorkspace key={session.session.session_id}/>
        : model === 'DGraFormer'
          ? <>
              <div className={immersive ? 'relative min-h-[920px] w-full overflow-hidden' : 'relative mx-auto grid max-w-[1400px] gap-6 px-5 py-10 lg:grid-cols-[280px_1fr_320px]'}>
                <div className={immersive ? 'absolute left-5 top-20 z-30 max-h-[760px] w-[280px] overflow-y-auto rounded-xl bg-white/90 p-4 shadow-xl' : ''}><ControlStudio/></div>
                <VisualizationCanvas/>
                {collapsed
                  ? <button onClick={() => setDemo('inspectorCollapsed', false)} className="absolute right-0 top-1/2"><ChevronLeft/></button>
                  : <div className={immersive ? 'absolute right-5 top-20 z-30 w-[320px] rounded-xl bg-white/90 p-4 shadow-xl' : 'relative'}><button onClick={() => setDemo('inspectorCollapsed', true)} className="absolute -left-7 top-1/2"><ChevronRight/></button><ExplanationInspector/></div>}
              </div>
              <DgraSelectionBridge/>
            </>
          : <MsgnetDataWorkspace/>}
    </section>
    <section id="validation-workspace" className="border-b border-line bg-[#f4f7fa]">
      <WorkspaceHeader number="02" title="Intervention Validation" text={imported ? 'Load only the stored evidence for the exact imported selection.' : 'Test the transferred relation against stored checkpoint-replayed evidence and matched controls.'}/>
      <div className="mx-auto max-w-[1240px] px-5 pt-6"><TransferBanner/></div>
      {imported
        ? <InterventionErrorBoundary><ImportedEvidenceWorkspace key={session.session.session_id}/></InterventionErrorBoundary>
        : pending
          ? model === 'DGraFormer'
            ? <InterventionErrorBoundary><CombinedInterventionLab/></InterventionErrorBoundary>
            : <InterventionErrorBoundary><MsgnetDiagnosticWorkspace/></InterventionErrorBoundary>
          : <div className="mx-auto max-w-[1240px] px-5 py-14 text-center text-[12px] text-ink-400">Select a candidate relation in Workspace 1, then choose “Test this relation”.</div>}
    </section>
    <SystemArchitecture/>
    <CaseStudy/>
    <Limitations/>
    <CitationSection/>
    <footer className="border-t border-line bg-white px-5 py-8 text-center text-[12px] text-ink-400">DGraInsight · Interactive evidence validation for learned graph structures in multivariate forecasting</footer>
  </div>;
}

function WorkspaceHeader({ number, title, text }: { number: string; title: string; text: string }) {
  return <div className="mx-auto max-w-[1400px] px-5 pt-12"><div className="eyebrow">Workspace {number}</div><h2 className="mt-2 font-serif text-[30px] font-semibold">{title}</h2><p className="mt-2 text-[12px] text-ink-400">{text}</p></div>;
}

function ModelSwitch({ value, onChange }: { value: WorkflowModel; onChange: (value: WorkflowModel) => void }) {
  return <div className="mx-auto flex max-w-[1400px] gap-2 px-5 py-5"><button onClick={() => onChange('DGraFormer')} className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[11px] font-semibold ${value === 'DGraFormer' ? 'bg-[#263b59] text-white' : 'border border-line bg-white'}`}><GitBranch size={14}/>DGraFormer · window graph</button><button onClick={() => onChange('MSGNet')} className={`flex items-center gap-2 rounded-lg px-4 py-2 text-[11px] font-semibold ${value === 'MSGNet' ? 'bg-[#263b59] text-white' : 'border border-line bg-white'}`}><Waves size={14}/>MSGNet · scale graph</button></div>;
}

function ImportedModelLock({ model, context }: { model: string; context: string }) {
  return <div className="mx-auto flex max-w-[1400px] px-5 py-5"><div className="inline-flex items-center gap-2 rounded-lg border border-[#16827f]/30 bg-[#edf7f6] px-4 py-2 text-[11px] font-semibold text-[#176e69]"><LockKeyhole size={13}/>{model} · {context} graph · fixed by imported session</div></div>;
}
