import { useMemo, useState, useEffect } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { buildAblationExplanation } from '@/engine/explanationEngine';
import { MetricBarChart } from './charts/MetricBarChart';
import { Tabs } from './ui/Tabs';
import { Select } from './ui/Select';
import type { AblationRow, AblationTable, DatasetId, Horizon } from '@/types/demo';
import { DATASET_IDS } from '@/data/datasets';
import { HORIZONS } from '@/data/paperMetrics';
import { oursMetric } from '@/data/paperMetrics';

const ABLATION = [
  { variant: 'Full' as const, label: 'Full DGraFormer', mse: 1.0, mae: 1.0, note: 'All components active: dynamic windows, dynamic graph, Top-K focusing, multi-scale Transformer.' },
  { variant: 'w/o DTW' as const, label: 'w/o Dynamic Time Windows', mse: 1.13, mae: 1.10, note: 'A single graph spans all time steps, so the model cannot track correlations that change between windows. This causes the largest accuracy drop.' },
  { variant: 'w/o DGL' as const, label: 'w/o Dynamic Graph Learning', mse: 1.085, mae: 1.07, note: 'Only the static seasonal prior C is used. The model loses the ability to adaptively learn window-specific correlations.' },
  { variant: 'w/o ECF' as const, label: 'w/o Essential Correlation Focusing', mse: 1.06, mae: 1.05, note: 'All positive edges propagate, so weak and spurious correlations inject noise into message passing.' },
  { variant: 'w/o MTE' as const, label: 'w/o Multi-scale Transformer Encoding', mse: 1.07, mae: 1.055, note: 'A single fixed patch size is used; patterns at other temporal resolutions are missed.' },
];

function generateAblation(dataset: DatasetId, horizon: Horizon): AblationTable {
  const base = oursMetric(dataset, horizon);
  return {
    dataset,
    horizon,
    rows: ABLATION.map((a) => ({
      variant: a.variant,
      label: a.label,
      mse: Math.round(base.mse * a.mse * 1000) / 1000,
      mae: Math.round(base.mae * a.mae * 1000) / 1000,
      note: a.note,
    })),
  };
}

export function AblationView() {
  const s = useDemoStore();
  const [metric, setMetric] = useState<'mse' | 'mae'>('mse');
  const [dataset, setDataset] = useState<DatasetId>(s.dataset);
  const [horizon, setHorizon] = useState<Horizon>(s.horizon);
  const [picked, setPicked] = useState<string | null>('Full DGraFormer');

  const table = useMemo(() => generateAblation(dataset, horizon), [dataset, horizon]);
  const full = table.rows.find((r) => r.variant === 'Full')!;
  const selectedRow: AblationRow | undefined = table.rows.find((r) => r.label === picked);

  useEffect(() => {
    if (!s.sample || !selectedRow) return;
    s.setExplanation(
      buildAblationExplanation(
        { sample: s.sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head },
        selectedRow.variant,
        selectedRow.label,
        selectedRow.mse,
        selectedRow.mae,
        full.mse,
        full.mae,
        selectedRow.note
      )
    );
  }, [picked, dataset, horizon, s.sample]);

  const bars = table.rows.map((r) => ({
    label: r.label,
    value: metric === 'mse' ? r.mse : r.mae,
    highlight: r.variant === 'Full',
    note: r.note,
  }));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[15px] font-semibold">Ablation study</h3>
        <div className="flex items-center gap-2">
          <Select<DatasetId>
            value={dataset}
            onChange={setDataset}
            options={DATASET_IDS.map((d) => ({ value: d, label: d }))}
            ariaLabel="Ablation dataset"
          />
          <Select<Horizon>
            value={horizon}
            onChange={setHorizon}
            options={HORIZONS.map((h) => ({ value: h, label: `h${h}` }))}
            ariaLabel="Ablation horizon"
          />
          <Tabs<'mse' | 'mae'>
            value={metric}
            onChange={setMetric}
            options={[
              { value: 'mse', label: 'MSE' },
              { value: 'mae', label: 'MAE' },
            ]}
            size="sm"
          />
        </div>
      </div>

      <MetricBarChart
        bars={bars}
        metricLabel={metric.toUpperCase()}
        selected={picked}
        baselineValue={metric === 'mse' ? full.mse : full.mae}
        onPick={setPicked}
      />

      <div className="mt-4 card p-4">
        <div className="eyebrow mb-1">{selectedRow ? selectedRow.label : 'Click a variant'}</div>
        <p className="text-[13.5px] leading-relaxed text-ink-700">
          {selectedRow
            ? selectedRow.note
            : 'Each bar removes one component. The Full model (highlighted) is the reference line; longer bars mean worse error. Removing dynamic time windows typically hurts most, confirming that per-window correlation modeling is the largest contributor.'}
        </p>
        {selectedRow && selectedRow.variant !== 'Full' && (
          <p className="mt-2 text-[12.5px] text-ink-400">
            Degradation vs. Full: {metricDelta(selectedRow, full, metric)} — this is the cost of dropping this
            component on {dataset} at horizon {horizon}.
          </p>
        )}
      </div>
    </div>
  );
}

function metricDelta(row: AblationRow, full: AblationRow, metric: 'mse' | 'mae'): string {
  const a = metric === 'mse' ? row.mse : row.mae;
  const b = metric === 'mse' ? full.mse : full.mae;
  const pct = ((a - b) / b) * 100;
  return `+${pct.toFixed(1)}% ${metric.toUpperCase()}`;
}
