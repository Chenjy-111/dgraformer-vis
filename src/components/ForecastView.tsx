import { useDemoStore } from '@/store/useDemoStore';
import { ForecastChart } from './ForecastChart';
import { buildForecastExplanation, buildWindowExplanation, buildErrorExplanation } from '@/engine/explanationEngine';
import { targetMetrics } from '@/engine/errorDiagnosis';
import { useEffect, useMemo } from 'react';

export function ForecastView() {
  const s = useDemoStore();
  const sample = s.sample;

  useEffect(() => {
    if (!sample) return;
    s.setExplanation(
      buildForecastExplanation({
        sample,
        windowIdx: s.windowIdx,
        target: s.target,
        depth: s.depth,
        scale: s.scale,
        head: s.head,
      })
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample?.dataset, sample?.sample_id, sample?.horizon, s.target]);

  if (!sample) return null;

  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const tm = useMemo(() => targetMetrics(sample, s.target), [sample, s.target]);

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-[15px] font-semibold">
          Forecast · {sample.variables[s.target]} <span className="text-ink-400">({sample.dataset})</span>
        </h3>
        <span className="data-num text-[12px] text-ink-400">
          MSE {tm.mse} · MAE {tm.mae}
        </span>
      </div>

      <ForecastChart
        sample={sample}
        variable={s.target}
        windowIdx={s.windowIdx}
        showPatchBoundary={s.showPatchBoundary}
        onPickWindow={(w) => {
          s.set('windowIdx', w);
          s.log('Pick window from forecast', undefined, `window ${w + 1}`);
          s.setExplanation(buildWindowExplanation({ ...ctx, windowIdx: w }));
        }}
        onPickStep={(step) => {
          s.set('selectedErrorStep', step);
          s.setView('error');
          s.log('Pick error step from forecast', undefined, `step ${step}`);
          s.setExplanation(buildErrorExplanation(ctx, step));
        }}
      />

      <div className="mt-3 grid grid-cols-2 gap-2 text-[12px] text-ink-500 sm:grid-cols-4">
        <Legend swatch="bg-history" label="History" />
        <Legend swatch="bg-truth" label="Ground truth" />
        <Legend swatch="bg-pred" label="Prediction" dashed />
        <Legend swatch="bg-errfill" label="Error band" />
      </div>
      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">
        Click inside the forecast region to inspect a step's error; click a look-back window band to load its
        dynamic graph. Patch boundaries mark the {sample.patchLen}-step patches used by the transformer.
      </p>
    </div>
  );
}

function Legend({ swatch, label, dashed }: { swatch: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-4 rounded-sm ${swatch} ${dashed ? 'opacity-80' : ''}`} />
      {label}
    </span>
  );
}
