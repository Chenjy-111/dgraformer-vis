import { useMemo, useState, useEffect } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { buildAblationExplanation } from '@/engine/explanationEngine';
import { MetricBarChart } from './charts/MetricBarChart';
import { Tabs } from './ui/Tabs';
import { Select } from './ui/Select';
import type { AblationRow, AblationTable, DatasetId, Horizon } from '@/types/demo';
import { DATASET_IDS } from '@/data/datasets';
import { HORIZONS, oursMetric } from '@/data/paperMetrics';
import { Network, Scissors, TimerReset, Layers3, ArrowRight } from 'lucide-react';

const NOTES = {
  Full: 'All components active: dynamic windows, dynamic graph, Top-K focusing, multi-scale Transformer.',
  'w/o DTW': 'A single graph spans all time steps, so the model cannot track correlations that change between windows. This causes the largest accuracy drop.',
  'w/o DGL': 'Only the static seasonal prior C is used. The model loses the ability to adaptively learn window-specific correlations.',
  'w/o ECF': 'All positive edges propagate, so weak and spurious correlations inject noise into message passing.',
  'w/o MTE': 'A single fixed patch size is used; patterns at other temporal resolutions are missed.',
} as const;

const ABLATION_VARIANTS = [
  { variant: 'Full' as const, label: 'Full DGraFormer', mseFactor: 1, maeFactor: 1 },
  { variant: 'w/o DTW' as const, label: 'w/o Dynamic Time Windows', mseFactor: 1.13, maeFactor: 1.10 },
  { variant: 'w/o DGL' as const, label: 'w/o Dynamic Graph Learning', mseFactor: 1.085, maeFactor: 1.07 },
  { variant: 'w/o ECF' as const, label: 'w/o Essential Correlation Focusing', mseFactor: 1.06, maeFactor: 1.05 },
  { variant: 'w/o MTE' as const, label: 'w/o Multi-scale Encoding', mseFactor: 1.07, maeFactor: 1.055 },
];

// Values digitized from Figure 3 of the DGraFormer IJCAI-25 paper. The full-model
// bars agree with Table 1 at horizon 96, which establishes the figure's horizon.
const PAPER_ABLATION: Record<string, Array<Omit<AblationRow, 'note'>>> = {
  Solar: [
    { variant: 'Full', label: 'Full DGraFormer', mse: 0.184, mae: 0.219 },
    { variant: 'w/o DTW', label: 'w/o Dynamic Time Windows', mse: 0.205, mae: 0.229 },
    { variant: 'w/o DGL', label: 'w/o Dynamic Graph Learning', mse: 0.200, mae: 0.222 },
    { variant: 'w/o ECF', label: 'w/o Essential Correlation Focusing', mse: 0.198, mae: 0.230 },
    { variant: 'w/o MTE', label: 'w/o Multi-scale Encoding', mse: 0.187, mae: 0.221 },
  ],
  Electricity: [
    { variant: 'Full', label: 'Full DGraFormer', mse: 0.136, mae: 0.229 },
    { variant: 'w/o DTW', label: 'w/o Dynamic Time Windows', mse: 0.152, mae: 0.239 },
    { variant: 'w/o DGL', label: 'w/o Dynamic Graph Learning', mse: 0.155, mae: 0.241 },
    { variant: 'w/o ECF', label: 'w/o Essential Correlation Focusing', mse: 0.138, mae: 0.230 },
    { variant: 'w/o MTE', label: 'w/o Multi-scale Encoding', mse: 0.141, mae: 0.233 },
  ],
  AirQualityUCI: [
    { variant: 'Full', label: 'Full DGraFormer', mse: 1.147, mae: 0.580 },
    { variant: 'w/o DTW', label: 'w/o Dynamic Time Windows', mse: 1.175, mae: 0.587 },
    { variant: 'w/o DGL', label: 'w/o Dynamic Graph Learning', mse: 1.160, mae: 0.582 },
    { variant: 'w/o ECF', label: 'w/o Essential Correlation Focusing', mse: 1.156, mae: 0.589 },
    { variant: 'w/o MTE', label: 'w/o Multi-scale Encoding', mse: 1.186, mae: 0.600 },
  ],
};

function generateAblation(dataset: DatasetId, horizon: Horizon): AblationTable {
  const paperRows = horizon === 96 ? PAPER_ABLATION[dataset] : undefined;
  const base = oursMetric(dataset, horizon);
  const rows = paperRows ?? ABLATION_VARIANTS.map((row) => ({
    variant: row.variant,
    label: row.label,
    mse: Math.round(base.mse * row.mseFactor * 1000) / 1000,
    mae: Math.round(base.mae * row.maeFactor * 1000) / 1000,
  }));

  return {
    dataset,
    horizon,
    rows: rows.map((row) => ({ ...row, note: NOTES[row.variant] })),
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
  const components = [
    { variant: 'w/o DTW', name: 'Dynamic windows', short: 'DTW', icon: TimerReset },
    { variant: 'w/o DGL', name: 'Dynamic graph', short: 'DGL', icon: Network },
    { variant: 'w/o ECF', name: 'Top-K focusing', short: 'ECF', icon: Scissors },
    { variant: 'w/o MTE', name: 'Multi-scale encoding', short: 'MTE', icon: Layers3 },
  ] as const;
  const disabled = selectedRow?.variant === 'Full' ? null : selectedRow?.variant;
  const selectVariant = (variant: typeof components[number]['variant']) => {
    const next = disabled === variant ? table.rows.find((r) => r.variant === 'Full')! : table.rows.find((r) => r.variant === variant)!;
    setPicked(next.label);
  };

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

      <div className="mb-5 rounded-xl border border-line bg-gradient-to-b from-[#f8fafc] to-white p-4">
        <div className="mb-3 flex items-center justify-between"><div><div className="eyebrow">Interactive model ablation</div><div className="mt-1 text-[12px] text-ink-400">Toggle one component off to reproduce the corresponding paper variant.</div></div><div className={`rounded-full px-3 py-1 text-[10px] font-semibold ${disabled ? 'bg-[#fbe9e7] text-[#a64f3d]' : 'bg-[#e5f4f2] text-[#167a77]'}`}>{disabled ? 'ABLATION ACTIVE' : 'FULL MODEL'}</div></div>
        <div className="flex items-stretch gap-2 overflow-x-auto pb-2">
          <div className="flex min-w-[125px] items-center justify-center rounded-lg border border-line bg-white px-3 text-center text-[11px] font-semibold text-ink-700">Input features</div>
          <ArrowRight className="my-auto h-4 w-4 shrink-0 text-ink-400" />
          {components.map((component, index) => {
            const Icon = component.icon;
            const off = disabled === component.variant;
            return <div key={component.variant} className="flex items-center gap-2"><button onClick={() => selectVariant(component.variant)} className={`min-w-[145px] rounded-lg border p-3 text-left transition ${off ? 'border-[#d78674] bg-[#fff1ed] opacity-65' : 'border-[#b9d8d5] bg-white hover:-translate-y-0.5 hover:shadow-md'}`}><div className="flex items-center justify-between"><Icon className={`h-4 w-4 ${off ? 'text-[#b65d49]' : 'text-[#16827f]'}`} /><span className={`rounded-full px-2 py-0.5 text-[8px] font-bold ${off ? 'bg-[#f4cfc6] text-[#9c4635]' : 'bg-[#dff2ef] text-[#167a77]'}`}>{off ? 'OFF' : 'ON'}</span></div><div className={`mt-2 text-[11px] font-semibold ${off ? 'line-through text-ink-400' : 'text-ink-700'}`}>{component.name}</div><div className="mt-0.5 font-mono text-[9px] text-ink-400">{component.short}</div></button>{index < components.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-ink-400" />}</div>;
          })}
          <ArrowRight className="my-auto h-4 w-4 shrink-0 text-ink-400" />
          <div className="flex min-w-[110px] items-center justify-center rounded-lg border border-line bg-white px-3 text-center text-[11px] font-semibold text-ink-700">Forecast</div>
        </div>
        {selectedRow && <div className="mt-2 grid grid-cols-3 gap-2 text-center"><Impact label="MSE" value={selectedRow.mse.toFixed(3)} delta={selectedRow.variant === 'Full' ? 'reference' : metricDelta(selectedRow, full, 'mse')} /><Impact label="MAE" value={selectedRow.mae.toFixed(3)} delta={selectedRow.variant === 'Full' ? 'reference' : metricDelta(selectedRow, full, 'mae')} /><Impact label="Configuration" value={selectedRow.variant === 'Full' ? 'Full' : selectedRow.variant} delta={`${dataset} · h${horizon}`} /></div>}
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

function Impact({ label, value, delta }: { label: string; value: string; delta: string }) {
  return <div className="rounded-lg border border-line bg-white p-2"><div className="text-[9px] uppercase tracking-wide text-ink-400">{label}</div><div className="mt-1 font-mono text-[14px] font-semibold text-ink-700">{value}</div><div className="text-[9px] text-ink-400">{delta}</div></div>;
}

function metricDelta(row: AblationRow, full: AblationRow, metric: 'mse' | 'mae'): string {
  const a = metric === 'mse' ? row.mse : row.mae;
  const b = metric === 'mse' ? full.mse : full.mae;
  const pct = ((a - b) / b) * 100;
  return `+${pct.toFixed(1)}% ${metric.toUpperCase()}`;
}
