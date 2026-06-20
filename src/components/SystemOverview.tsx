import { useState } from 'react';
import { Section } from './layout/Section';
import { ArrowRight } from 'lucide-react';
import { cn } from './ui/cn';

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
    output: 'A structured explanation in the inspector and the narrative report.',
    why: 'Turns model internals into inspectable, attributable evidence for the demo audience.',
    viz: 'The right-hand Explanation Inspector, always visible in the workspace.',
  },
];

export function SystemOverview() {
  const [active, setActive] = useState(0);
  const s = STAGES[active];
  return (
    <Section
      id="overview"
      eyebrow="System overview"
      title="The DGraFormer explanation pipeline"
      intro="Click any stage to see what it does, its inputs and outputs, why it helps forecasting, and how this demo visualizes it."
    >
      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <div className="card p-4">
          <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
            {STAGES.map((st, i) => (
              <div key={st.key} className="flex items-center">
                <button
                  onClick={() => setActive(i)}
                  className={cn(
                    'rounded-md border px-2.5 py-1.5 text-left text-[12.5px] leading-tight transition focus-visible:focus-ring',
                    i === active
                      ? 'border-accent bg-accent-soft text-accent-deep font-medium'
                      : 'border-line bg-white text-ink-500 hover:border-accent/50 hover:text-ink-700'
                  )}
                >
                  {st.label}
                </button>
                {i < STAGES.length - 1 && <ArrowRight className="mx-0.5 h-3.5 w-3.5 text-ink-400" />}
              </div>
            ))}
          </div>
        </div>

        <div className="card p-5">
          <div className="eyebrow mb-1">Stage {active + 1} / {STAGES.length}</div>
          <h3 className="font-serif text-[20px] font-semibold leading-tight">{s.label}</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-700">{s.does}</p>
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
