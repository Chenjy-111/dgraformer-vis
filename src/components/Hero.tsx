import { ArrowRight, FlaskConical, PlayCircle } from 'lucide-react';
import { Button } from './ui/Button';
import { useWorkflowStore } from '@/store/useWorkflowStore';
import { useDemoStore } from '@/store/useDemoStore';

export function Hero() {
  const runGuidedExample = useWorkflowStore(s => s.runGuidedExample);
  const setDemo = useDemoStore(s => s.set);
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  return <section id="top" className="border-b border-line bg-white">
    <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-16 lg:grid-cols-[1.1fr_.9fr] lg:py-20">
      <div><div className="eyebrow mb-3">Interactive evidence validation for learned graph structures</div>
        <h1 className="font-serif text-[42px] font-semibold leading-none tracking-tight md:text-[56px]">DGra<span className="text-accent">Insight</span></h1>
        <p className="mt-5 max-w-2xl text-[20px] leading-snug text-ink-800">Learned graphs are easy to visualize, but difficult to validate.</p>
        <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-ink-500">DGraInsight lets forecasting researchers discover a candidate learned relation, carry that exact selection into a checkpoint-replayed graph intervention, compare the response with matched controls, and obtain a provenance-backed, bounded evidence record.</p>
        <div className="mt-7 flex flex-wrap gap-2.5">
          <Button variant="primary" icon={<ArrowRight size={15}/>} onClick={() => scrollTo('discovery-workspace')}>Explore graph patterns</Button>
          <Button variant="outline" icon={<FlaskConical size={15}/>} onClick={() => scrollTo('validation-workspace')}>Inspect intervention evidence</Button>
          <Button variant="outline" icon={<PlayCircle size={15}/>} onClick={() => { runGuidedExample(); setDemo('sampleId',0); setDemo('windowIdx',0); setDemo('selectedEdge',{source:0,target:4}); setDemo('view','graph'); scrollTo('discovery-workspace'); }}>Start guided example</Button>
        </div>
      </div>
      <div className="card p-6"><div className="eyebrow">The reviewer question</div><p className="mt-3 font-serif text-[25px] leading-snug text-[#263b59]">Does a learned graph relation actually matter to the model's forecast?</p><div className="mt-6 grid grid-cols-3 gap-2 text-center text-[11px] font-semibold"><div className="rounded-lg bg-[#edf7f6] p-3 text-accent">Discover</div><div className="rounded-lg bg-[#eef2f7] p-3 text-[#263b59]">Test</div><div className="rounded-lg bg-[#f8f2e8] p-3 text-amber-800">Validate</div></div><p className="mt-4 text-[11px] leading-relaxed text-ink-400">The output describes the tested checkpoint's behavior. It does not establish a causal relationship between real-world variables.</p></div>
    </div>
  </section>;
}
