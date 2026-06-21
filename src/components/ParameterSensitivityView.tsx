import { useDemoStore } from '@/store/useDemoStore';
import { Tabs } from './ui/Tabs';
import type { DatasetId } from '@/types/demo';
import { DATASET_IDS } from '@/data/datasets';

export function ParameterSensitivityView() {
  const s = useDemoStore();

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
          <Tabs<DatasetId>
            value={s.sensitivityDataset}
            onChange={(d) => s.set('sensitivityDataset', d as 'ETTh1')}
            options={DATASET_IDS.map((d) => ({ value: d, label: d }))}
            size="sm"
          />
        </div>
      </div>

      <div className="card flex min-h-[300px] items-center justify-center p-6 text-[13px] text-ink-400">
        Run training with varying hyperparameters to populate real sensitivity curves.
      </div>
    </div>
  );
}
