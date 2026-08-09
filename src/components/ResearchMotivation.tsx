import { Section } from './layout/Section';
import { AcademicCard } from './layout/AcademicCard';

const PROBLEMS = [
  { title: 'Too many graphs to inspect manually', body: 'Multiple datasets, samples, windows, and variable pairs create thousands of graph relationships. Researchers need a systematic way to find candidate patterns worth testing.' },
  { title: 'Graph weight is not functional evidence', body: 'A visually strong or frequently retained edge may have little effect on the forecast. Model-internal intervention is required to measure what changes when that edge is removed.' },
  { title: 'One intervention can be accidental', body: 'A measured change has meaning only relative to matched real-edge controls and a transparent statistical protocol. Negative results must remain visible rather than being filtered out.' },
];

export function ResearchMotivation() {
  return <Section id="motivation" eyebrow="Problem & user value" title="Why dynamic-graph interpretation needs validation" intro="The system is built for dynamic-graph forecasting researchers who need to move from visual inspection to testable, reproducible model evidence.">
    <div className="grid gap-4 md:grid-cols-3">{PROBLEMS.map((problem,index)=><AcademicCard key={problem.title} index={`0${index+1}`} title={problem.title}><p className="text-[14px] leading-relaxed text-ink-500">{problem.body}</p></AcademicCard>)}</div>
    <p className="mt-6 max-w-3xl text-[14px] leading-relaxed text-ink-500">DGraInsight first discovers structural candidates, then modifies the selected graph window, reruns the real checkpoint, measures prediction and error changes, and compares them with matched controls. Its conclusions describe model behavior under specified conditions—not real-world causal relationships.</p>
  </Section>;
}
