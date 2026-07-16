import { useState } from 'react';
import { Section } from './layout/Section';
import { ArrowRight } from 'lucide-react';
import { cn } from './ui/cn';
import { useDemoStore } from '@/store/useDemoStore';
import { Activity, Network, Scissors, Share2, Layers3, Sigma, LineChart, Database } from 'lucide-react';

interface Stage {
  key: string;
  label: string;
  does: string;
  input: string;
  output: string;
  why: string;
  viz: string;
}

const STAGES: Stage[] = [
  {
    key: 'input',
    label: 'Input history',
    does: 'Takes the multivariate look-back window X of N variables over T=96 steps and instance-normalizes it.',
    input: 'Raw multivariate series X ∈ R^{N×T}.',
    output: 'Normalized series ready for graph and temporal modeling.',
    why: 'Instance normalization mitigates distribution shift between train and test segments.',
    viz: 'Shown as the gray history curve in the Forecast view.',
  },
  {
    key: 'partition',
    label: 'Dynamic window partition',
    does: 'Divides the look-back into W windows of m steps, each assumed to have stable internal correlations.',
    input: 'Normalized series.',
    output: 'W time windows, each receiving its own graph.',
    why: 'Correlations drift over time; per-window modeling captures that drift instead of averaging it away.',
    viz: 'The window slider and window overlays select which partition you are inspecting.',
  },
  {
    key: 'prior',
    label: 'Static seasonal prior C',
    does: 'Builds a global correlation prior from the seasonal signal: DFT → Top-Kf frequencies → IDFT → cosine similarity.',
    input: 'Full training series.',
    output: 'Prior correlation matrix C ∈ R^{N×N}.',
    why: 'Removing trend and keeping seasonal structure gives a stable correlation prior that prevents random-init overfitting.',
    viz: 'Selectable as "Static Prior C" in the Dynamic Graph view.',
  },
  {
    key: 'dynamic',
    label: 'Window dynamic graph Ew',
    does: 'Mixes the prior with a learnable per-window graph: Ew = αC + (1−α)Rw, with α decaying 0.9 → 0.1.',
    input: 'Prior C and learnable node embeddings Rw.',
    output: 'Window-specific correlation graph Ew.',
    why: 'Lets each window express its own evolving relationships while staying anchored to a sensible prior early in training.',
    viz: 'The default "Window Dynamic Graph Ew" view; compare windows with the slider.',
  },
  {
    key: 'topk',
    label: 'Top-K essential focusing',
    does: 'Keeps only the top-Ke correlation weights via a mask Mw, zeroing the rest: Ẽw = Mw ⊙ Ew.',
    input: 'Dynamic graph Ew.',
    output: 'Sparse essential graph Ẽw.',
    why: 'Filters spurious/weak edges so message passing concentrates on essential correlations.',
    viz: 'The Top-K Focusing view shows before/after and the kept vs filtered edge lists.',
  },
  {
    key: 'mp',
    label: 'Graph message passing',
    does: 'Mix-hop GCN with residual: H(l) = βH(0) + (1−β)·A·H(l−1), selecting features across hops.',
    input: 'Sparse graphs A and normalized features.',
    output: 'Correlation-aware representation Hout.',
    why: 'Aggregates information along essential edges while preserving each node\u2019s own signal.',
    viz: 'Edge explanations describe which variables propagate to your target.',
  },
  {
    key: 'mtt',
    label: 'Multi-scale temporal transformer',
    does: 'Patches each series (p=8), then pairwise-combines patches across layers to read 3 temporal scales with multi-head attention.',
    input: 'Correlation-aware representation.',
    output: 'Multi-scale temporal features.',
    why: 'A single patch size misses some resolutions; multi-scale captures short fluctuation, periodicity and long trend.',
    viz: 'The Multi-Scale Attention view shows per-scale, per-head attention maps.',
  },
  {
    key: 'forecast',
    label: 'Forecasting output',
    does: 'Flattens and linearly projects the fused representation to the τ-step forecast Y.',
    input: 'Multi-scale temporal features.',
    output: 'Forecast Y ∈ R^{N×τ}.',
    why: 'Combines correlation and temporal evidence into the final prediction.',
    viz: 'The red dashed prediction curve against the blue ground truth.',
  },
  {
    key: 'explain',
    label: 'Interactive explanation',
    does: 'Surfaces evidence, formulas, assumptions and caveats tied to whatever you select.',
    input: 'Any selection: window, edge, node, patch, error step.',
    output: 'A structured explanation in the inspector.',
    why: 'Turns model internals into inspectable, attributable evidence for the demo audience.',
    viz: 'The right-hand Explanation Inspector, always visible in the workspace.',
  },
];

export function SystemOverview() {
  const [active, setActive] = useState(0);
  const demo = useDemoStore();
  const sample = demo.sample;
  const s = STAGES[active];
  const icons = [Database, Layers3, Sigma, Network, Scissors, Share2, Activity, LineChart, LineChart];
  const goToStage = () => {
    const view = s.key === 'dynamic' || s.key === 'topk' || s.key === 'mp' ? 'graph' : s.key === 'mtt' ? 'attention' : s.key === 'forecast' ? 'forecast' : null;
    if (view) { demo.setView(view); document.getElementById('workspace')?.scrollIntoView({ behavior: 'smooth' }); }
  };
  return (
    <Section
      id="overview"
      eyebrow="System overview"
      title="The DGraFormer explanation pipeline"
      intro="Click any stage to see what it does, its inputs and outputs, why it helps forecasting, and how this demo visualizes it."
    >
      <div className="card overflow-hidden border-[#d8e0e9] bg-gradient-to-br from-white to-[#f3f7fa] p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4 text-[11px] text-ink-400">
          <span>Live configuration</span>
          <div className="flex flex-wrap gap-2"><span className="rounded bg-white px-2 py-1 shadow-sm">Input {sample?.variables.length ?? 7} × {sample?.history[0]?.length ?? 96}</span><span className="rounded bg-white px-2 py-1 shadow-sm">Windows {sample?.windows.length ?? 7}</span><span className="rounded bg-white px-2 py-1 shadow-sm">Patch {sample?.patchLen ?? 8}</span><span className="rounded bg-white px-2 py-1 shadow-sm">Horizon {sample?.horizon ?? 96}</span></div>
        </div>
        <div className="overflow-x-auto pb-4">
          <div className="relative flex min-w-[1180px] items-stretch gap-3 px-2 pt-4">
            <div className="absolute left-8 right-8 top-[59px] h-[2px] bg-gradient-to-r from-[#94a3b8] via-[#16827f] to-[#d6453b] opacity-35" />
            {STAGES.map((st, i) => (
              <div key={st.key} className="relative z-10 flex min-w-[115px] flex-1 items-center">
                <button
                  onClick={() => setActive(i)}
                  className={cn(
                    'group h-[108px] w-full rounded-xl border p-3 text-left transition duration-300 focus-visible:focus-ring',
                    i === active
                      ? 'scale-[1.04] border-accent bg-white text-accent-deep shadow-[0_10px_30px_rgba(28,124,122,.15)]'
                      : 'border-line bg-white/90 text-ink-500 hover:-translate-y-1 hover:border-accent/50 hover:text-ink-700 hover:shadow-md'
                  )}
                >
                  {(() => { const Icon = icons[i] ?? Activity; return <Icon className={`mb-2 h-5 w-5 ${i === active ? 'text-accent' : 'text-ink-400'}`} />; })()}
                  <span className="block text-[11px] font-semibold leading-tight">{st.label}</span>
                  <span className="mt-1 block font-mono text-[8.5px] text-ink-400">{i === 0 ? `N×${sample?.history[0]?.length ?? 96}` : i === STAGES.length - 1 ? `N×${sample?.horizon ?? 96}` : 'feature flow'}</span>
                </button>
                {i < STAGES.length - 1 && <ArrowRight className="-mx-1 h-4 w-4 shrink-0 text-accent" />}
              </div>
            ))}
          </div>
        </div>
        <div className="mt-2 grid gap-4 rounded-xl border border-line bg-white p-5 lg:grid-cols-[1.3fr_1fr]">
          <div>
          <div className="eyebrow mb-1">Stage {active + 1} / {STAGES.length}</div>
          <h3 className="font-serif text-[20px] font-semibold leading-tight">{s.label}</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-700">{s.does}</p>
          <button onClick={goToStage} className="mt-4 rounded-md bg-[#263b59] px-3 py-2 text-[11px] font-semibold text-white transition hover:bg-[#16827f]">Open linked visualization →</button>
          </div>
          <dl className="mt-4 space-y-2 text-[13px]">
            <Row term="Input" desc={s.input} />
            <Row term="Output" desc={s.output} />
            <Row term="Why it helps" desc={s.why} />
            <Row term="In this demo" desc={s.viz} />
          </dl>
      </div>
      </div>
    </Section>
  );
}

function Row({ term, desc }: { term: string; desc: string }) {
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3">
      <dt className="text-ink-400">{term}</dt>
      <dd className="text-ink-700">{desc}</dd>
    </div>
  );
}
