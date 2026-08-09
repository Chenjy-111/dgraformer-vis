import { ArrowRight, Compass, Network, Workflow } from 'lucide-react';
import { Button } from './ui/Button';
import { useDemoStore } from '@/store/useDemoStore';

const CHAIN = ['Real checkpoint', 'Candidate pattern', 'Window intervention', 'Matched controls', 'Evidence trace'];

export function Hero() {
  const startTour = useDemoStore((s) => s.startTour);
  const setView = useDemoStore((s) => s.setView);
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });

  return <section id="top" className="border-b border-line bg-white">
    <div className="mx-auto grid max-w-[1400px] gap-10 px-5 py-16 lg:grid-cols-[1.05fr_0.95fr] lg:py-20">
      <div>
        <div className="eyebrow mb-3">Dynamic graph pattern discovery · evidence validation</div>
        <h1 className="font-serif text-[40px] font-semibold leading-[1.05] tracking-tight md:text-[52px]">DGra<span className="text-accent">Insight</span></h1>
        <p className="mt-3 max-w-xl text-[17px] leading-snug text-ink-700">Discover graph patterns. Test them with real interventions.</p>
        <p className="mt-5 max-w-xl text-[14.5px] leading-relaxed text-ink-500">A research workflow for finding candidate relationships in DGraFormer, rerunning the real checkpoint under graph interventions, comparing effects with matched controls, and tracing every conclusion back to its data, model, graph, and experiment record.</p>
        <div className="mt-7 flex flex-wrap gap-2.5">
          <Button variant="primary" icon={<ArrowRight size={15}/>} onClick={() => { setView('forecast'); scrollTo('workspace'); }}>Explore real sample</Button>
          <Button variant="outline" icon={<Compass size={15}/>} onClick={startTour}>Start guided tour</Button>
          <Button variant="outline" icon={<Workflow size={15}/>} onClick={() => scrollTo('intervention-lab')}>Run precomputed intervention</Button>
          <Button variant="outline" icon={<Network size={15}/>} onClick={() => scrollTo('intervention-lab')}>Watch evidence unfold</Button>
        </div>
        <div className="mt-8 flex flex-wrap gap-x-8 gap-y-2 text-[12.5px] text-ink-500"><Stat k="1" v="supported dataset · ETTh1"/><Stat k="5" v="checkpoint-replayed samples"/><Stat k="4,000" v="real-edge control records"/><Stat k="0.0" v="identity replay Δmax"/></div>
      </div>
      <div className="card flex flex-col justify-center p-6">
        <div className="eyebrow mb-4">The evidence chain</div>
        <ol className="relative ml-3 border-l border-dashed border-line">{CHAIN.map((step,i)=><li key={step} className="relative mb-3 pl-5 last:mb-0"><span className="absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-white bg-accent"/><div className="flex items-center gap-2"><span className="data-num text-[11px] text-ink-400">{String(i+1).padStart(2,'0')}</span><span className="text-[13.5px] font-medium text-ink-900">{step}</span></div></li>)}</ol>
        <p className="mt-4 text-[12px] leading-relaxed text-ink-400">Graph weight is only a candidate signal. A stronger claim requires a real intervention, matched controls, statistics, and a complete reproduction trace.</p>
      </div>
    </div>
  </section>;
}

function Stat({k,v}:{k:string;v:string}){return <div className="flex items-baseline gap-1.5"><span className="font-serif text-[20px] font-semibold text-accent">{k}</span><span>{v}</span></div>}
