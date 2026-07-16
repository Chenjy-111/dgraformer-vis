import { Section } from './layout/Section';
import { useDemoStore } from '@/store/useDemoStore';
import type { ViewMode } from '@/types/demo';
import { Activity, GitGraph, Filter, Grid3x3, AlertTriangle, LineChart, FileText } from 'lucide-react';

const MODES: { view: ViewMode; label: string; blurb: string; Icon: typeof Activity }[] = [
  { view: 'forecast', label: 'Forecast', blurb: 'History, ground truth and prediction with error band and window overlays.', Icon: Activity },
  { view: 'graph', label: 'Dynamic graph', blurb: 'Per-window inter-variable graph as nodes/edges or a matrix; evolve across windows.', Icon: GitGraph },
  { view: 'topk', label: 'Top-K focusing', blurb: 'Before/after sparsification with kept vs filtered edges and the noise-reduction story.', Icon: Filter },
  { view: 'attention', label: 'Multi-scale attention', blurb: 'Patch-to-patch attention at three scales and four heads, linked to the forecast.', Icon: Grid3x3 },
  { view: 'error', label: 'Error diagnosis', blurb: 'Error over the horizon with diagnostic clues tied to graph and attention signals.', Icon: AlertTriangle },
  { view: 'sensitivity', label: 'Parameter sensitivity', blurb: 'How window size m, focusing ratio Ke and prior weight α affect accuracy.', Icon: LineChart },
  { view: 'narrative', label: 'Narrative report', blurb: 'An auto-generated, exportable explanation report for the current selection.', Icon: FileText },
];

export function ExplanationModeGallery() {
  const setView = useDemoStore((s) => s.setView);
  function go(v: ViewMode) {
    setView(v);
    document.getElementById('workspace')?.scrollIntoView({ behavior: 'smooth' });
  }
  return (
    <Section
      id="modes"
      eyebrow="Explanation modes"
      title="Seven ways to interrogate the model"
      intro="Each mode answers a different question. Pick one to jump straight into the workspace with that view active."
    >
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {MODES.map(({ view, label, blurb, Icon }) => (
          <button
            key={view}
            onClick={() => go(view)}
            className="card p-4 text-left transition hover:-translate-y-0.5 hover:shadow-pop focus-visible:focus-ring"
          >
            <Icon className="h-5 w-5 text-accent" />
            <div className="mt-2 text-[14px] font-semibold">{label}</div>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-500">{blurb}</p>
          </button>
        ))}
      </div>
    </Section>
  );
}
