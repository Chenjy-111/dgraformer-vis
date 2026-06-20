import { useEffect } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { ErrorTimeline } from './charts/ErrorTimeline';
import { topErrorPeaks, meanErrorSeries, horizonErrorGrowth } from '@/engine/errorDiagnosis';
import { buildErrorExplanation } from '@/engine/explanationEngine';
import { Button } from './ui/Button';

export function ErrorDiagnosisView() {
  const s = useDemoStore();
  const sample = s.sample;

  const step = s.selectedErrorStep ?? Math.floor((sample?.horizon ?? 96) / 2);

  useEffect(() => {
    if (sample) s.setExplanation(buildErrorExplanation({ sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head }, step));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample?.sample_id, s.target, s.selectedErrorStep]);

  if (!sample) return null;
  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const err = meanErrorSeries(sample, s.target);
  const peaks = topErrorPeaks(sample, s.target, 5);
  const growth = horizonErrorGrowth(sample, s.target);

  const pick = (st: number) => {
    s.set('selectedErrorStep', st);
    // jump to nearest look-back window for context
    const nearest = Math.min(sample.windows.length - 1, Math.floor((st / sample.horizon) * sample.windows.length));
    s.set('windowIdx', nearest);
    s.log('Pick error peak', undefined, `step ${st}`);
    s.setExplanation(buildErrorExplanation(ctx, st));
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-semibold">Error diagnosis · {sample.variables[s.target]}</h3>
        <span className="data-num text-[12px] text-ink-400">
          early {growth.early} → late {growth.late}
        </span>
      </div>

      <ErrorTimeline error={err} onPick={pick} selected={s.selectedErrorStep} peaks={peaks.map((p) => p.step)} />

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.1fr]">
        <div className="card p-3">
          <div className="eyebrow mb-2">Top error steps</div>
          <ul className="space-y-1">
            {peaks.map((p) => {
              const sel = s.selectedErrorStep === p.step;
              return (
                <li key={p.step}>
                  <button
                    onClick={() => pick(p.step)}
                    className={`flex w-full items-center justify-between rounded-md border px-2.5 py-1.5 text-[12.5px] transition focus-visible:focus-ring ${
                      sel ? 'border-accent bg-accent-soft' : 'border-line bg-white hover:border-accent/50'
                    }`}
                  >
                    <span>future step {p.step}</span>
                    <span className="data-num text-pred">err {p.value}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="card p-4">
          <div className="eyebrow mb-2">Diagnostic clues (correlational, not causal)</div>
          <p className="text-[13px] leading-relaxed text-ink-700">
            Selecting a peak loads the nearest look-back window so you can inspect its dynamic graph and attention.
            Clues combine model-internal signals (graph stability, sparsity, attention concentration) with the
            observed error.
          </p>
          <div className="mt-3 flex gap-2">
            <Button size="sm" variant="outline" onClick={() => s.setView('graph')}>
              Open window graph
            </Button>
            <Button size="sm" variant="outline" onClick={() => s.setView('attention')}>
              Open attention
            </Button>
          </div>
        </div>
      </div>

      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">
        Possible error sources surfaced as clues: weakly-retained edges, an unstable dynamic graph, an over-filtered
        useful edge, long-horizon uncertainty, or low attention concentration. These are diagnostic hints, never
        strict causal explanations.
      </p>
    </div>
  );
}
