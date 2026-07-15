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
import { useDemoStore } from './store/useDemoStore';
import { useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export default function App() {
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
      <div id="workspace" className={`border-b border-line ${immersive3D ? 'bg-[#eef3f8]' : 'bg-white'}`}>
        <div className={immersive3D
          ? 'relative min-h-[920px] w-full overflow-hidden'
          : `relative mx-auto grid gap-6 px-5 py-14 transition-all ${inspectorCollapsed ? 'max-w-[1540px] lg:grid-cols-[280px_1fr]' : 'max-w-[1400px] lg:grid-cols-[280px_1fr_320px]'}`}>
          {immersive3D && <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-24 bg-gradient-to-b from-[#eef3f8] to-transparent" />}
          <div className={immersive3D ? 'absolute left-5 top-24 z-30 max-h-[760px] w-[280px] overflow-y-auto rounded-xl border border-white/80 bg-white/90 p-4 shadow-[0_18px_55px_rgba(35,48,71,.16)] backdrop-blur-xl' : ''}>
          <ControlStudio />
          </div>
          <VisualizationCanvas />
          {inspectorCollapsed ? (
            <button
              onClick={() => setStore('inspectorCollapsed', false)}
              title="Show explanation panel"
              className={`absolute right-0 z-40 flex h-11 w-7 items-center justify-center rounded-l-lg border border-r-0 border-[#cbd4df] bg-white text-[#56657b] shadow-md transition hover:bg-[#edf4f4] hover:text-[#16827f] ${immersive3D ? 'top-24' : 'top-14'}`}
            >
              <ChevronLeft className="h-4 w-4" />
              <span className="sr-only">Show explanation panel</span>
            </button>
          ) : (
            <div className={immersive3D
              ? 'absolute right-5 top-24 z-30 max-h-[760px] w-[320px] overflow-visible rounded-xl border border-white/80 bg-white/90 p-4 shadow-[0_18px_55px_rgba(35,48,71,.16)] backdrop-blur-xl'
              : 'relative'}>
              <button
                onClick={() => setStore('inspectorCollapsed', true)}
                title="Hide explanation panel and enlarge visualization"
                className={`absolute -left-7 z-40 flex h-11 w-7 items-center justify-center rounded-l-lg border border-r-0 border-[#cbd4df] bg-white text-[#56657b] shadow-md transition hover:bg-[#edf4f4] hover:text-[#16827f] ${immersive3D ? 'top-4' : 'top-0'}`}
              >
                <ChevronRight className="h-4 w-4" />
                <span className="sr-only">Hide explanation panel</span>
              </button>
              <div className={immersive3D ? 'max-h-[728px] overflow-y-auto' : ''}>
                <ExplanationInspector />
              </div>
            </div>
          )}
        </div>
      </div>
      <ExplanationModeGallery />
      <CaseStudy />
      <Limitations />
      <CitationSection />
      <footer className="border-t border-line bg-white px-5 py-8 text-center text-[12px] text-ink-400">
        DGraFormer-Vis · IJCAI-25 Demo Track · Interactive Explanation System for Dynamic Graph Learning
      </footer>
    </div>
  );
}
