import { Hero } from './components/Hero';
import { SystemOverview } from './components/SystemOverview';
import { MethodExplainer } from './components/MethodExplainer';
import { ExplanationModeGallery } from './components/ExplanationModeGallery';
import { VisualizationCanvas } from './components/VisualizationCanvas';
import { ControlStudio } from './components/ControlStudio';
import { ExplanationInspector } from './components/ExplanationInspector';
import { CaseStudy } from './components/CaseStudy';
import { ResearchMotivation } from './components/ResearchMotivation';
import { Limitations } from './components/Limitations';
import { CitationSection } from './components/CitationSection';
import { InterventionErrorBoundary } from './components/InterventionErrorBoundary';
import { CombinedInterventionLab } from './components/CombinedInterventionLab';
import { useDemoStore } from './store/useDemoStore';
import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, GitBranch, Waves } from 'lucide-react';
import { MsgnetDataWorkspace, MsgnetDiagnosticWorkspace } from './components/MsgnetWorkspace';

export default function App() {
  const [dataModel, setDataModel] = useState<'DGraFormer' | 'MSGNet'>('DGraFormer');
  const [diagnosticModel, setDiagnosticModel] = useState<'DGraFormer' | 'MSGNet'>('DGraFormer');
  const loadCurrent = useDemoStore((s) => s.loadCurrent);
  const immersive3D = useDemoStore((s) => s.view === 'graph' && s.graphLayout === '3d-timeline');
  const inspectorCollapsed = useDemoStore((s) => s.inspectorCollapsed);
  const setStore = useDemoStore((s) => s.set);

  useEffect(() => {
    loadCurrent();
  }, [loadCurrent]);

  return (
    <div className="min-h-screen bg-paper">
      <Hero />
      <ResearchMotivation />
      <SystemOverview />
      <MethodExplainer />
      <ModelSwitch id="workspace" eyebrow="Data exploration" description="Forecast and learned graph views" value={dataModel} onChange={setDataModel} />
      <div className={dataModel === 'DGraFormer' ? 'block' : 'hidden'} aria-hidden={dataModel !== 'DGraFormer'}>
      <div className={`border-b border-line ${immersive3D ? 'bg-[#eef3f8]' : 'bg-white'}`}>
        <div className={immersive3D
          ? 'relative min-h-[920px] w-full overflow-hidden'
          : `relative mx-auto grid gap-6 px-5 py-14 transition-all ${inspectorCollapsed ? 'max-w-[1540px] lg:grid-cols-[280px_1fr]' : 'max-w-[1400px] lg:grid-cols-[280px_1fr_320px]'}`}>
          {immersive3D && <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-24 bg-gradient-to-b from-[#eef3f8] to-transparent" />}
          <div className={immersive3D ? 'absolute left-5 top-24 z-30 max-h-[760px] w-[280px] overflow-y-auto rounded-xl border border-white/80 bg-white/90 p-4 shadow-[0_18px_55px_rgba(35,48,71,.16)] backdrop-blur-xl' : ''}>
          <ControlStudio />
          </div>
          <VisualizationCanvas />
          {inspectorCollapsed ? (
            <button onClick={() => setStore('inspectorCollapsed', false)} title="Show explanation panel" className="absolute right-0 top-1/2 z-40 flex h-11 w-7 -translate-y-1/2 items-center justify-center rounded-l-lg border border-r-0 border-[#cbd4df] bg-white text-[#56657b] shadow-md"><ChevronLeft className="h-4 w-4"/><span className="sr-only">Show explanation panel</span></button>
          ) : (
            <div className={immersive3D ? 'absolute right-5 top-24 z-30 max-h-[760px] w-[320px] overflow-visible rounded-xl border border-white/80 bg-white/90 p-4 shadow-[0_18px_55px_rgba(35,48,71,.16)] backdrop-blur-xl' : 'relative'}>
              <button onClick={() => setStore('inspectorCollapsed', true)} title="Hide explanation panel and enlarge visualization" className="absolute -left-7 top-1/2 z-40 flex h-11 w-7 -translate-y-1/2 items-center justify-center rounded-l-lg border border-r-0 border-[#cbd4df] bg-white text-[#56657b] shadow-md"><ChevronRight className="h-4 w-4"/><span className="sr-only">Hide explanation panel</span></button>
              <div className={immersive3D ? 'max-h-[728px] overflow-y-auto' : ''}><ExplanationInspector /></div>
            </div>
          )}
        </div>
      </div>
      </div>
      <div className={dataModel === 'MSGNet' ? 'block' : 'hidden'} aria-hidden={dataModel !== 'MSGNet'}><MsgnetDataWorkspace /></div>

      <ModelSwitch id="diagnostic-workspace-switch" eyebrow="Edge intervention & diagnosis" description="Stored pruning responses and bounded conclusions" value={diagnosticModel} onChange={setDiagnosticModel} />
      <div className={diagnosticModel === 'DGraFormer' ? 'block' : 'hidden'} aria-hidden={diagnosticModel !== 'DGraFormer'}><InterventionErrorBoundary><CombinedInterventionLab /></InterventionErrorBoundary></div>
      <div className={diagnosticModel === 'MSGNet' ? 'block' : 'hidden'} aria-hidden={diagnosticModel !== 'MSGNet'}><InterventionErrorBoundary><MsgnetDiagnosticWorkspace /></InterventionErrorBoundary></div>
      <ExplanationModeGallery />
      <CaseStudy />
      <Limitations />
      <CitationSection />
      <footer className="border-t border-line bg-white px-5 py-8 text-center text-[12px] text-ink-400">
        DGraInsight · ETTh1 audited precomputed evidence · No browser-generated scientific values
      </footer>
    </div>
  );
}

function ModelSwitch({id,eyebrow,description,value,onChange}:{id:string;eyebrow:string;description:string;value:'DGraFormer'|'MSGNet';onChange:(v:'DGraFormer'|'MSGNet')=>void}) {
 return <div id={id} className="border-b border-line bg-[#f4f6f7] px-5 py-5"><div className="mx-auto flex max-w-[1400px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><div className="eyebrow">{eyebrow}</div><p className="mt-1 text-[11px] text-ink-400">{description} · model states remain independent</p></div><div className="inline-flex w-fit rounded-xl border border-[#cbd4df] bg-white p-1 shadow-sm" role="group" aria-label={`${eyebrow} model`}><ModelButton active={value==='DGraFormer'} onClick={()=>onChange('DGraFormer')} label="DGraFormer" detail="Dynamic graph" icon={<GitBranch size={15}/>}/><ModelButton active={value==='MSGNet'} onClick={()=>onChange('MSGNet')} label="MSGNet" detail="Scale graph" icon={<Waves size={15}/>}/></div></div></div>
}
function ModelButton({ active, onClick, label, detail, icon }: { active: boolean; onClick: () => void; label: string; detail: string; icon: React.ReactNode }) {
  return <button type="button" aria-pressed={active} onClick={onClick} className={`flex min-w-[145px] items-center gap-2 rounded-lg px-4 py-2 text-left transition ${active ? 'bg-[#263b59] text-white shadow-sm' : 'text-[#56657b] hover:bg-[#edf4f4]'}`}>
    <span className={active ? 'text-[#70d0ca]' : 'text-[#16827f]'}>{icon}</span>
    <span><span className="block text-[12px] font-semibold">{label}</span><span className={`block text-[9px] ${active ? 'text-white/55' : 'text-ink-400'}`}>{detail}</span></span>
  </button>;
}
