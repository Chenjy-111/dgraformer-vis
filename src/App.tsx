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

  useEffect(() => {
    loadCurrent();
  }, [loadCurrent]);

  return (
    <div className="min-h-screen bg-paper">
      <Hero />
      <ResearchMotivation />
      <SystemOverview />
      <MethodExplainer />
      <div id="workspace" className="border-b border-line bg-white">
        <div className="mx-auto grid max-w-[1400px] gap-6 px-5 py-14 lg:grid-cols-[280px_1fr_320px]">
          <ControlStudio />
          <VisualizationCanvas />
          <ExplanationInspector />
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
