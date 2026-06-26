import { Section } from './layout/Section';
import { KatexSpan } from './KatexSpan';

export function MethodExplainer() {
  return (
    <Section
      id="method"
      eyebrow="Model mechanism"
      title="Two components, one explanation chain"
      intro="DGraFormer pairs Dynamic Correlation-aware Graph Learning (DCGL) with a Multi-Scale Temporal Transformer (MTT). The formulas below are the ones this demo visualizes."
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="card p-6">
          <div className="eyebrow mb-1">Component A</div>
          <h3 className="font-serif text-[21px] font-semibold">Dynamic Correlation-aware Graph Learning</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-500">
            DCGL learns a correlation graph per window, then keeps only the essential edges.
          </p>
          <div className="mt-4 space-y-3">
            <Formula
              caption="Seasonal prior from the frequency domain"
              expr="X_{sea} = \text{IDFT}(\,\text{argTopK}_{K_f}(|\text{DFT}(X_{all})|), A, \Phi\,)"
            />
            <Formula caption="Cosine-similarity prior matrix" expr="C = X_{sea} \cdot X_{sea}^T \;/\; (\|X_{sea}\| \cdot \|X_{sea}\|^T)" />
            <Formula
              caption="Window graph: prior mixed with learnable dynamic graph"
              expr="E_w = \alpha \cdot C + (1-\alpha) \cdot R_w,\quad \alpha \in [0.1,0.9]"
            />
            <Formula caption="Top-Ke essential focusing mask" expr="\tilde{E}_w = M_w \odot E_w,\quad M_w = \text{reshape}(\mathbf{1}_{\text{argTopK}_{K_e}(\text{vec}(E_w))})" />
            <Formula caption="Mix-hop message passing with residual" expr="H^{(l)} = \beta \cdot H^{(0)} + (1-\beta) \cdot A \cdot H^{(l-1)}" />
          </div>
        </div>

        <div className="card p-6">
          <div className="eyebrow mb-1">Component B</div>
          <h3 className="font-serif text-[21px] font-semibold">Multi-Scale Temporal Transformer</h3>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-500">
            MTT patches each series and reads temporal structure at progressively coarser scales.
          </p>
          <div className="mt-4 space-y-3">
            <Formula caption="Patch embedding (p = 8 steps per patch)" expr="\bar{x}^i = W_p \cdot h^i_p + W_{pos}" />
            <Formula caption="Scaled dot-product self-attention over patches" expr="z^i_a = \text{softmax}\!\left( Q^i K^{iT} / \sqrt{d_k} \right) \cdot V^i" />
            <Formula caption="Pairwise patch combination across layers" expr="X_p^{(l)} = \text{reshape}\!\left(Z^{(l-1)},\; [\,N,\; 2D^{(l-1)},\; S^{(l-1)}/2\,]\right)" />
          </div>
          <div className="mt-5 grid grid-cols-3 gap-2 text-center text-[12px]">
            <ScaleChip n="Scale 1" sub="8-step patches" note="local fluctuation" />
            <ScaleChip n="Scale 2" sub="16-step patches" note="periodic pattern" />
            <ScaleChip n="Scale 3" sub="32-step patches" note="long-range trend" />
          </div>
        </div>
      </div>
    </Section>
  );
}

function Formula({ caption, expr }: { caption: string; expr: string }) {
  return (
    <div>
      <div className="text-[12px] text-ink-400">{caption}</div>
      <div className="mt-1 rounded-md bg-paper px-3 py-2 text-[12.5px] text-ink-900">
        <KatexSpan tex={expr} block />
      </div>
    </div>
  );
}

function ScaleChip({ n, sub, note }: { n: string; sub: string; note: string }) {
  return (
    <div className="rounded-md border border-line bg-paper px-2 py-2">
      <div className="font-semibold text-ink-700">{n}</div>
      <div className="data-num text-[11px] text-ink-400">{sub}</div>
      <div className="mt-0.5 text-ink-500">{note}</div>
    </div>
  );
}
