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

export default function App() {
  const loadCurrent = useDemoStore((s) => s.loadCurrent);
  const immersive3D = useDemoStore((s) => s.view === 'graph' && s.graphLayout === '3d-timeline');

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
          : 'mx-auto grid max-w-[1400px] gap-6 px-5 py-14 lg:grid-cols-[280px_1fr_320px]'}>
          {immersive3D && <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-24 bg-gradient-to-b from-[#eef3f8] to-transparent" />}
          <div className={immersive3D ? 'absolute left-5 top-24 z-30 max-h-[760px] w-[280px] overflow-y-auto rounded-xl border border-white/80 bg-white/90 p-4 shadow-[0_18px_55px_rgba(35,48,71,.16)] backdrop-blur-xl' : ''}>
          <ControlStudio />
          </div>
          <VisualizationCanvas />
          <div className={immersive3D ? 'absolute right-5 top-24 z-30 max-h-[760px] w-[320px] overflow-y-auto rounded-xl border border-white/80 bg-white/90 p-4 shadow-[0_18px_55px_rgba(35,48,71,.16)] backdrop-blur-xl' : ''}>
          <ExplanationInspector />
          </div>
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
