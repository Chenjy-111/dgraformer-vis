import { Section } from './layout/Section';
import { useDemoStore } from '@/store/useDemoStore';
import type { DatasetId, Horizon, ViewMode } from '@/types/demo';
import { Button } from './ui/Button';
import { ArrowRight } from 'lucide-react';

interface Case {
  title: string;
  question: string;
  body: string;
  dataset: DatasetId;
  sampleId: number;
  horizon: Horizon;
  view: ViewMode;
}

const CASES: Case[] = [
  {
    title: 'Does the graph really change per window?',
    question: 'Dynamic vs static correlation',
    body:
      'Load ETTh1 and step the window slider while watching the dynamic graph. The static prior C is identical ' +
      'in every window; Ew is not. Switching to the difference view highlights exactly where each window departs ' +
      'from the prior.',
    dataset: 'ETTh1',
    sampleId: 0,
    horizon: 96,
    view: 'graph',
  },
  {
    title: 'What does Top-K focusing actually remove?',
    question: 'Noise reduction',
    body:
      'On Solar, open the Top-K view. The before graph is dense; after focusing only a fraction of edges survive. ' +
      'Click a filtered edge to see why it reads as weak/spurious, and a kept edge to see why it carries signal.',
    dataset: 'Solar',
    sampleId: 0,
    horizon: 96,
    view: 'topk',
  },
  {
    title: 'Where does the forecast go wrong, and why?',
    question: 'Error diagnosis',
    body:
      'On Weather, open Error Diagnosis. Click the largest error peak: the demo jumps to the nearest window and ' +
      'surfaces diagnostic clues — unstable edges, over-filtering, or low attention concentration — as correlational hints.',
    dataset: 'Weather',
    sampleId: 0,
    horizon: 96,
    view: 'error',
  },
];

export function CaseStudy() {
  const setCase = useDemoStore((s) => s.setCase);
  const setView = useDemoStore((s) => s.setView);

  function run(c: Case) {
    setCase({ dataset: c.dataset, sampleId: c.sampleId, horizon: c.horizon });
    setView(c.view);
    document.getElementById('workspace')?.scrollIntoView({ behavior: 'smooth' });
  }

  return (
    <Section
      id="cases"
      eyebrow="Case studies"
      title="Guided scenarios for the demo audience"
      intro="Each scenario loads a specific case and view so you can reproduce a finding in one click."
    >
      <div className="grid gap-4 md:grid-cols-3">
        {CASES.map((c) => (
          <div key={c.title} className="card flex flex-col p-5">
            <div className="eyebrow mb-1">{c.question}</div>
            <h3 className="text-[16px] font-semibold leading-snug">{c.title}</h3>
            <p className="mt-2 flex-1 text-[13px] leading-relaxed text-ink-500">{c.body}</p>
            <div className="mt-4">
              <Button variant="outline" size="sm" icon={<ArrowRight className="h-3.5 w-3.5" />} onClick={() => run(c)}>
                Open this case
              </Button>
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}
