import { useDemoStore } from '@/store/useDemoStore';
import { ForecastChart } from './ForecastChart';
import { buildForecastExplanation, buildForecastStepExplanation, buildWindowExplanation } from '@/engine/explanationEngine';
import { targetMetrics, topErrorPeaks, meanErrorSeries, horizonErrorGrowth } from '@/engine/errorDiagnosis';
import { useEffect, useMemo } from 'react';
import { ErrorTimeline } from './charts/ErrorTimeline';
import { Select } from './ui/Select';

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

  useEffect(() => {
    if (!sample) return;
    const firstPeak = topErrorPeaks(sample, s.target, 1)[0];
    if (!firstPeak) return;
    const nearest = Math.min(sample.windows.length - 1, Math.floor((firstPeak.step / sample.horizon) * sample.windows.length));
    s.set('selectedErrorStep', firstPeak.step);
    s.set('windowIdx', nearest);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample?.dataset, sample?.sample_id, sample?.horizon, s.target]);

  if (!sample) return null;

  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const tm = useMemo(() => targetMetrics(sample, s.target), [sample, s.target]);
  const err = useMemo(() => meanErrorSeries(sample, s.target), [sample, s.target]);
  const peaks = useMemo(() => topErrorPeaks(sample, s.target, 5), [sample, s.target]);
  const growth = useMemo(() => horizonErrorGrowth(sample, s.target), [sample, s.target]);
  const selectedStep = s.selectedErrorStep;
  const evidenceWindowIdx = selectedStep == null ? s.windowIdx : Math.min(sample.windows.length - 1, Math.floor((selectedStep / sample.horizon) * sample.windows.length));
  const evidenceWindow = sample.windows[evidenceWindowIdx];
  const keyEdges = [...evidenceWindow.kept_edges].sort((a, b) => b.weight - a.weight).slice(0, 3);

  const pickStep = (step: number) => {
    const nearest = Math.min(sample.windows.length - 1, Math.floor((step / sample.horizon) * sample.windows.length));
    s.set('selectedErrorStep', step);
    s.set('windowIdx', nearest);
    s.log('Pick forecast diagnostic step', undefined, `step ${step}`);
    s.setExplanation(buildForecastStepExplanation({ ...ctx, windowIdx: nearest }, step));
  };

  return (
    <div className="flex flex-col">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h3 className="text-[15px] font-semibold whitespace-nowrap">
            Forecast · {sample.variables[s.target]} <span className="text-ink-400">({sample.dataset})</span>
          </h3>
          <Select<number>
            value={s.sampleId}
            onChange={(n) => s.setCase({ sampleId: n })}
            options={[0, 1, 2, 3, 4].map((n) => ({ value: n, label: `sample ${n}` }))}
            ariaLabel="Sample"
          />
        </div>
        <span className="data-num text-[12px] text-ink-400 whitespace-nowrap">
          MSE {tm.mse} · MAE {tm.mae}
        </span>
      </div>

      <div className="order-2 mt-5 border-t border-line pt-5">
      <ForecastChart
        sample={sample}
        variable={s.target}
        windowIdx={s.windowIdx}
        showPatchBoundary={s.showPatchBoundary}
        selectedFutureStep={selectedStep}
        onPickWindow={(w) => {
          s.set('windowIdx', w);
          s.log('Pick window from forecast', undefined, `window ${w + 1}`);
          s.setExplanation(buildWindowExplanation({ ...ctx, windowIdx: w }));
        }}
        onPickStep={(step) => {
          pickStep(step);
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

      <div className="order-1 mt-2 rounded-xl border border-line bg-gradient-to-b from-[#f8fafc] to-white p-4">
        <div className="mb-3 flex items-baseline justify-between"><div><div className="eyebrow">Prediction diagnostics</div><h4 className="mt-1 text-[14px] font-semibold">Residual timeline and evidence links</h4></div><span className="font-mono text-[11px] text-ink-400">early {growth.early} → late {growth.late}</span></div>
        <ErrorTimeline error={err} onPick={pickStep} selected={selectedStep} peaks={peaks.map((p) => p.step)} />
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1.15fr]">
          <div className="rounded-lg border border-line bg-paper p-3">
            <div className="eyebrow mb-2">Top error peaks</div>
            <div className="grid grid-cols-5 gap-1.5">{peaks.map((p) => <button key={p.step} onClick={() => pickStep(p.step)} className={`rounded-md border px-1 py-2 text-center transition ${selectedStep === p.step ? 'border-pred bg-[#fbe9e7]' : 'border-line bg-white hover:border-pred/50'}`}><span className="block text-[9px] text-ink-400">+{p.step}</span><b className="font-mono text-[10px] text-pred">{p.value}</b></button>)}</div>
          </div>
          <div className="rounded-lg border border-line bg-white p-3">
            <div className="eyebrow mb-2">Linked model evidence {selectedStep == null ? '(select a forecast point)' : `for step +${selectedStep}`}</div>
            <div className="grid gap-2 sm:grid-cols-3">
              <Evidence label="History context" value={`Window ${evidenceWindowIdx + 1} · steps ${evidenceWindow.start}–${evidenceWindow.end}`} />
              <Evidence label="Temporal scale" value={`Scale ${s.scale} · Head ${s.head}`} />
              <Evidence label="Absolute error" value={selectedStep == null ? '—' : (sample.error[s.target]?.[selectedStep] ?? 0).toFixed(4)} danger />
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">{keyEdges.map((edge) => <button key={`${edge.source}-${edge.target}`} onClick={() => { s.set('selectedEdge', { source: edge.source, target: edge.target }); s.setView('graph'); }} className="rounded-full border border-[#b9d8d5] bg-[#edf7f6] px-2 py-1 text-[10px] font-medium text-[#167a77]">{sample.variables[edge.source]} → {sample.variables[edge.target]} · {edge.weight.toFixed(2)}</button>)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Evidence({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return <div className="rounded-md bg-paper px-2.5 py-2"><div className="text-[9px] uppercase tracking-wide text-ink-400">{label}</div><div className={`mt-1 text-[11px] font-semibold ${danger ? 'text-pred' : 'text-ink-700'}`}>{value}</div></div>;
}

function Legend({ swatch, label, dashed }: { swatch: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-4 rounded-sm ${swatch} ${dashed ? 'opacity-80' : ''}`} />
      {label}
    </span>
  );
}
