import { useMemo, useState } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { SensitivityLineChart } from './charts/SensitivityLineChart';
import { Tabs } from './ui/Tabs';
import type { SensitivityCurve } from '@/types/demo';

function ushape(x: number[], best: number, depth: number, floor: number): number[] {
  const span = Math.max(...x) - Math.min(...x) || 1;
  return x.map((v) => {
    const d = Math.abs(v - best) / span;
    return Math.round(floor * (1 + depth * d * d) * 10000) / 10000;
  });
}

function generateSensitivity(
  param: 'm' | 'Ke' | 'alpha',
  dataset: 'Weather' | 'Solar'
): SensitivityCurve {
  const floorMse = dataset === 'Weather' ? 0.168 : 0.184;
  const floorMae = dataset === 'Weather' ? 0.207 : 0.219;

  if (param === 'm') {
    const x = [24, 72, 144, 423, 1008];
    return {
      param, dataset, x, best: 144,
      mse: ushape(x, 144, 0.10, floorMse),
      mae: ushape(x, 144, 0.08, floorMae),
      note: 'Best around m = 144 (one day): within-day correlations are stable, while larger windows mix changing relationships.',
    };
  }
  if (param === 'Ke') {
    const x = [0.5, 0.1, 0.05, 0.01, 0.005];
    return {
      param, dataset, x, best: 0.05,
      mse: ushape(x, 0.05, 0.13, floorMse),
      mae: ushape(x, 0.05, 0.10, floorMae),
      note: 'A moderate Ke removes redundant noise; too small discards essential edges and weakens the model.',
    };
  }
  const x = [0.1, 0.3, 0.5, 0.7, 0.9];
  return {
    param, dataset, x, best: 0.5,
    mse: ushape(x, 0.5, 0.03, floorMse),
    mae: ushape(x, 0.5, 0.025, floorMae),
    note: 'Performance is stable across alpha; graph learning adaptively compensates for the prior-vs-dynamic mixing ratio.',
  };
}

const PARAM_LABEL: Record<'m' | 'Ke' | 'alpha', string> = {
  m: 'm — time points per window',
  Ke: 'Ke — weight focusing ratio',
  alpha: 'α — static prior proportion',
};

export function ParameterSensitivityView() {
  const s = useDemoStore();
  const [showMse, setShowMse] = useState(true);
  const [showMae, setShowMae] = useState(true);

  const curve = useMemo(
    () => generateSensitivity(s.sensitivityParam, s.sensitivityDataset),
    [s.sensitivityParam, s.sensitivityDataset]
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[15px] font-semibold">Parameter sensitivity</h3>
        <div className="flex items-center gap-2">
          <Tabs<'m' | 'Ke' | 'alpha'>
            value={s.sensitivityParam}
            onChange={(p) => s.set('sensitivityParam', p)}
            options={[
              { value: 'm', label: 'm' },
              { value: 'Ke', label: 'Ke' },
              { value: 'alpha', label: 'α' },
            ]}
            size="sm"
          />
          <Tabs<'Weather' | 'Solar'>
            value={s.sensitivityDataset}
            onChange={(d) => s.set('sensitivityDataset', d)}
            options={[
              { value: 'Weather', label: 'Weather' },
              { value: 'Solar', label: 'Solar' },
            ]}
            size="sm"
          />
        </div>
      </div>

      <div className="mb-3 flex items-center gap-3 text-[12px]">
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={showMse} onChange={(e) => setShowMse(e.target.checked)} /> MSE
        </label>
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={showMae} onChange={(e) => setShowMae(e.target.checked)} /> MAE
        </label>
        <span className="ml-auto data-num text-ink-400">{PARAM_LABEL[s.sensitivityParam]}</span>
      </div>

      <SensitivityLineChart
        x={curve.x}
        mse={curve.mse}
        mae={curve.mae}
        best={curve.best}
        xLabel={PARAM_LABEL[s.sensitivityParam]}
        showMse={showMse}
        showMae={showMae}
      />

      <div className="mt-4 card p-4">
        <div className="eyebrow mb-1">Reading this curve</div>
        <p className="text-[13.5px] leading-relaxed text-ink-700">{curve.note}</p>
        <p className="mt-2 text-[12.5px] text-ink-400">
          Best value marked at {s.sensitivityParam} = {curve.best}. For m, a one-day window keeps within-day
          correlations stable; for Ke, moderate sparsity removes noise without discarding useful edges; for α,
          performance is flat because graph learning adapts regardless of the prior's weight.
        </p>
      </div>
    </div>
  );
}
