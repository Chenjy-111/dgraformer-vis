import { useEffect } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { AttentionHeatmap } from './charts/AttentionHeatmap';
import { ForecastChart } from './ForecastChart';
import { getScale, headMatrix, patchRange, attentionConcentration, strongestLink } from '@/engine/attentionAnalysis';
import { buildPatchExplanation } from '@/engine/explanationEngine';
import type { ScaleId } from '@/types/demo';

const SCALE_NOTE: Record<ScaleId, string> = {
  1: 'Scale 1 — short-term local fluctuation (fine patches).',
  2: 'Scale 2 — periodic patterns (medium patches).',
  3: 'Scale 3 — long-range trend (coarse patches).',
};

export function MultiScaleAttentionView() {
  const s = useDemoStore();
  const sample = s.sample;

  useEffect(() => {
    if (sample) s.setExplanation(buildPatchExplanation({ sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head }, 0, 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample?.sample_id, s.scale, s.head]);

  if (!sample) return null;
  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const sc = getScale(sample, s.scale);
  const mat = headMatrix(sc, s.head);
  const conc = attentionConcentration(mat);
  const strong = strongestLink(mat);

  // map selected/hovered patch to look-back step range for forecast highlight
  let highlight: [number, number] | null = null;
  if (s.linkAttention && s.hoveredPatch) {
    const [qs] = patchRange(sc, s.hoveredPatch.q);
    const [, ke] = patchRange(sc, s.hoveredPatch.k);
    highlight = [Math.min(qs, patchRange(sc, s.hoveredPatch.k)[0]), Math.max(ke, patchRange(sc, s.hoveredPatch.q)[1])];
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-semibold">
          Multi-scale attention · scale {s.scale} · head {s.head}
        </h3>
        <span className="data-num text-[12px] text-ink-400">
          {sc.patchSteps}-step patches · {sc.nPatches} patches · concentration {conc}
        </span>
      </div>

      <div className="flex flex-col items-center">
        <AttentionHeatmap
          matrix={mat}
          patchLabel={(i) => `P${i + 1}`}
          selected={s.hoveredPatch}
          onHoverCell={(q, k) => s.set('hoveredPatch', { q, k })}
          onClickCell={(q, k) => {
            s.set('hoveredPatch', { q, k });
            s.log('Click attention cell', undefined, `scale ${s.scale} P${q + 1}→P${k + 1}`);
            s.setExplanation(buildPatchExplanation(ctx, q, k));
          }}
          size={Math.min(380, 120 + sc.nPatches * 24)}
          title={`Scale ${s.scale} · head ${s.head}`}
        />
        <p className="mt-2 max-w-md text-center text-[12px] text-ink-400">{SCALE_NOTE[s.scale]}</p>

        <div className="mt-6 w-full max-w-lg">
          <div className="eyebrow mb-2 text-center">{s.linkAttention ? 'Linked forecast (hover a cell)' : 'Forecast'}</div>
          <ForecastChart
            sample={sample}
            variable={s.target}
            windowIdx={s.windowIdx}
            showPatchBoundary
            highlightPatches={highlight}
          />
        </div>

        <div className="mt-3 max-w-lg rounded-md border border-line bg-paper p-3 text-[12.5px] text-ink-500">
          Strongest link in this head: <span className="font-mono text-ink-700">P{strong.q + 1} → P{strong.k + 1}</span>{' '}
          (weight {strong.w.toFixed(2)}). Darker cells mean a query patch (row) draws more from a key patch (column).
          Compare heads and scales to see how local vs. periodic vs. trend evidence is combined.
        </div>
      </div>
    </div>
  );
}
