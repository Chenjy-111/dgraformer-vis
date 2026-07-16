import { Section } from './layout/Section';

const ITEMS = [
  {
    h: 'Precomputed, not live',
    b: 'The demo loads exported local DGraFormer inference artifacts; it does not run inference in the browser. These per-sample values are real bundled outputs, but they are not the paper\u2019s dataset-level aggregate metrics.',
  },
  {
    h: 'Diagnostic, not causal',
    b: 'Edge weights are learned correlation strengths used for feature aggregation, not causal effects. Error explanations combine model-internal signals with observed error and are presented as clues, never as proofs of cause.',
  },
  {
    h: 'Visualization-oriented simplifications',
    b: 'Window counts and node sets are clamped for legibility, so a small graph here may correspond to a larger graph in the full model. Attention maps show representative scales/heads, not every layer.',
  },
  {
    h: 'No model comparison platform',
    b: 'Baseline numbers are included for context, but this is an explanation system for one model, not a benchmarking tool. It does not let you train, tune, or upload data.',
  },
];

export function Limitations() {
  return (
    <Section
      id="limitations"
      eyebrow="Scope & limitations"
      title="What this demo is and is not"
      intro="Being explicit about scope keeps the explanations honest — a core requirement for an interpretability demo."
    >
      <div className="grid gap-4 md:grid-cols-2">
        {ITEMS.map((it) => (
          <div key={it.h} className="card p-5">
            <h3 className="text-[15px] font-semibold">{it.h}</h3>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-500">{it.b}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}
