import { useMemo } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { ForecastChart } from './ForecastChart';
import { Select } from './ui/Select';

export function ForecastView() {
  const s = useDemoStore();
  const sample = s.sample;
  const metrics = useMemo(() => sample ? targetMetrics(sample.ground_truth[s.target] ?? [], sample.prediction[s.target] ?? []) : null, [sample, s.target]);

  if (!sample || !metrics) return null;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h3 className="whitespace-nowrap text-[15px] font-semibold">
            Forecast · {sample.variables[s.target]} <span className="text-ink-400">({sample.dataset})</span>
          </h3>
          <Select<number>
            value={s.sampleId}
            onChange={(n) => s.setCase({ sampleId: n })}
            options={[0, 1, 2, 3, 4].map((n) => ({ value: n, label: `sample ${n}` }))}
            ariaLabel="Sample"
          />
        </div>
        <span className="data-num whitespace-nowrap text-[12px] text-ink-400">
          target MSE {metrics.mse.toFixed(6)} · target MAE {metrics.mae.toFixed(6)}
        </span>
      </div>

      <ForecastChart
        sample={sample}
        variable={s.target}
        windowIdx={s.windowIdx}
        showPatchBoundary={s.showPatchBoundary}
        onPickWindow={(windowIdx) => {
          s.set('windowIdx', windowIdx);
          s.log('Select look-back window', undefined, `window ${windowIdx + 1}`);
        }}
      />

      <div className="mt-3 grid grid-cols-2 gap-2 text-[12px] text-ink-500 sm:grid-cols-4">
        <Legend swatch="bg-history" label="History" />
        <Legend swatch="bg-truth" label="Ground truth" />
        <Legend swatch="bg-pred" label="Prediction" dashed />
        <Legend swatch="bg-errfill" label="Absolute residual band" />
      </div>
      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">
        Curves and metrics are deterministic descriptions of stored checkpoint outputs. Selecting a look-back band changes only the displayed graph context; the interface does not attribute forecast errors to that window.
      </p>
    </div>
  );
}

function targetMetrics(truth: number[], prediction: number[]) {
  const length = Math.min(truth.length, prediction.length);
  if (length === 0) return { mse: 0, mae: 0 };
  let squared = 0;
  let absolute = 0;
  for (let index = 0; index < length; index += 1) {
    const error = prediction[index] - truth[index];
    squared += error * error;
    absolute += Math.abs(error);
  }
  return { mse: squared / length, mae: absolute / length };
}

function Legend({ swatch, label, dashed }: { swatch: string; label: string; dashed?: boolean }) {
  return <span className="inline-flex items-center gap-1.5"><span className={`inline-block h-2.5 w-4 rounded-sm ${swatch} ${dashed ? 'opacity-80' : ''}`} />{label}</span>;
}
