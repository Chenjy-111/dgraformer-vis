import { Section } from './layout/Section';
import { ArrowRight } from 'lucide-react';

const stages = [
  ['Input','Checkpoint, sample, graph'],
  ['Discover','Explore graph contexts'],
  ['Select','Choose a relation'],
  ['Test','Replay its removal'],
  ['Validate','Compare with controls'],
  ['Output','Evidence with provenance'],
];
export function SystemOverview(){return <Section id="overview" eyebrow="Workflow" title="One relation, one continuous test" intro="Discover a relation, then test that exact relation."><div className="card p-5"><div className="flex overflow-x-auto">{stages.map(([title,body],i)=><div key={title} className="flex min-w-[185px] flex-1 items-center"><div className="min-h-[116px] flex-1 rounded-xl border border-line bg-white p-4"><div className="text-[9px] font-semibold uppercase tracking-wider text-accent">{String(i+1).padStart(2,'0')}</div><h3 className="mt-2 text-[15px] font-semibold">{title}</h3><p className="mt-2 text-[10px] leading-relaxed text-ink-400">{body}</p></div>{i<stages.length-1&&<ArrowRight className="mx-2 shrink-0 text-accent" size={16}/>}</div>)}</div></div></Section>}
