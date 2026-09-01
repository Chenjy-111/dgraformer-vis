import { ArrowRight, FlaskConical, PlayCircle } from 'lucide-react';
import { Button } from './ui/Button';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useDemoStore } from '@/store/useDemoStore';
import { useAuditSessionStore } from '@/store/useAuditSessionStore';

export function Hero() {
  const runGuidedExample = useWorkflowStore(s => s.runGuidedExample);
  const testRelation = useWorkflowStore(s => s.testRelation);
  const setDemo = useDemoStore(s => s.set);
  const imported = useAuditSessionStore(s => s.source === 'imported');
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  const loadAuditedExample = (openEvidence: boolean) => {
    if (imported) {
      scrollTo(openEvidence ? 'validation-workspace' : 'discovery-workspace');
      return;
    }
    runGuidedExample();
    setDemo('sampleId', 0);
    setDemo('windowIdx', 0);
    setDemo('selectedEdge', { source: 0, target: 4 });
    setDemo('view', 'graph');
    if (openEvidence) testRelation();
    setTimeout(() => scrollTo(openEvidence ? 'validation-workspace' : 'discovery-workspace'), 0);
  };
  return <section id="top" className="border-b border-line bg-white">
    <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-16 lg:grid-cols-[1.1fr_.9fr] lg:py-20">
      <div><div className="eyebrow mb-3">Validate learned graph structures</div>
        <h1 className="font-serif text-[42px] font-semibold leading-none tracking-tight md:text-[56px]">DGra<span className="text-accent">Insight</span></h1>
        <p className="mt-5 max-w-2xl text-[20px] leading-snug text-ink-800">See a learned relation, test it, and inspect the evidence.</p>
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-ink-500">Select a relation, replay its removal, and compare the response with matched controls.</p>
        <div className="mt-7 flex flex-wrap gap-2.5">
          <Button variant="primary" icon={<ArrowRight size={15}/>} onClick={() => scrollTo('discovery-workspace')}>Explore graph patterns</Button>
          <Button variant="outline" icon={<FlaskConical size={15}/>} onClick={() => loadAuditedExample(true)}>{imported ? 'Inspect imported evidence' : 'Inspect intervention evidence'}</Button>
          <Button variant="outline" icon={<PlayCircle size={15}/>} onClick={() => loadAuditedExample(false)}>{imported ? 'Explore imported session' : 'Start guided example'}</Button>
        </div>
      </div>
      <div className="card p-6"><div className="eyebrow">The reviewer question</div><p className="mt-3 font-serif text-[25px] leading-snug text-[#263b59]">Does this relation affect the model's forecast?</p><div className="mt-6 grid grid-cols-3 gap-2 text-center text-[11px] font-semibold"><div className="rounded-lg bg-[#edf7f6] p-3 text-accent">Discover</div><div className="rounded-lg bg-[#eef2f7] p-3 text-[#263b59]">Test</div><div className="rounded-lg bg-[#f8f2e8] p-3 text-amber-800">Validate</div></div><p className="mt-4 text-[11px] leading-relaxed text-ink-400">Evidence describes model behavior, not real-world causality.</p></div>
    </div>
  </section>;
}
