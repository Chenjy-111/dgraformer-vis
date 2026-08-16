import { Section } from './layout/Section';
import { ArrowRight } from 'lucide-react';

const stages = [
  ['Input','Trained checkpoint, test sample, learned graph'],
  ['Discover','Explore forecasts and model-specific graph contexts'],
  ['Select','Choose one candidate learned relation'],
  ['Test','Load the exact checkpoint-replayed relation removal'],
  ['Validate','Compare against matched controls and corrected statistics'],
  ['Output','Bounded evidence record with provenance'],
];
export function SystemOverview(){return <Section id="overview" eyebrow="System at a glance" title="One continuous evidence-validation workflow" intro="Workspace 1 finds a relation worth testing. Workspace 2 tests the exact same relation."><div className="card p-5"><div className="flex overflow-x-auto">{stages.map(([title,body],i)=><div key={title} className="flex min-w-[185px] flex-1 items-center"><div className="min-h-[116px] flex-1 rounded-xl border border-line bg-white p-4"><div className="text-[9px] font-semibold uppercase tracking-wider text-accent">{String(i+1).padStart(2,'0')}</div><h3 className="mt-2 text-[15px] font-semibold">{title}</h3><p className="mt-2 text-[10px] leading-relaxed text-ink-400">{body}</p></div>{i<stages.length-1&&<ArrowRight className="mx-2 shrink-0 text-accent" size={16}/>}</div>)}</div></div></Section>}
