import { useEffect, type ReactNode } from 'react';
import { Pause, Play, RotateCcw, FileDown } from 'lucide-react';
import { useDemoStore } from '@/store/useDemoStore';
import { DATASETS } from '@/data/datasets';
import { download } from '@/engine/narrativeGenerator';
import { Select } from './ui/Select';
import { Slider } from './ui/Slider';
import { Toggle } from './ui/Toggle';
import { Tabs } from './ui/Tabs';
import { Button } from './ui/Button';
import type { GraphLayout, GraphSource, ScaleId, ViewMode } from '@/types/demo';

export function ControlStudio() {
  const s = useDemoStore();
  const sample = s.sample;
  const nWindows = sample?.windows.length ?? 1;

  useEffect(() => {
    if (!s.playing) return;
    const id = setInterval(() => {
      const state = useDemoStore.getState();
      state.set('windowIdx', (state.windowIdx + 1) % (state.sample?.windows.length ?? 1));
    }, 1100);
    return () => clearInterval(id);
  }, [s.playing]);

  const variableOptions = sample?.variables.map((label, value) => ({ value, label }))
    ?? DATASETS[s.dataset].variables.map((label, value) => ({ value, label }));

  return (
    <div className="space-y-5">
      <Group title="Case">
        <div className="text-[12px] text-ink-500">Dataset: ETTh1 · {DATASETS.ETTh1.variables.length} variables</div>
        <Field label="Target variable">
          <Select<number>
            value={s.target}
            onChange={(target) => {
              s.set('target', target);
              s.log('Change target', undefined, sample?.variables[target]);
            }}
            options={variableOptions}
            ariaLabel="Target variable"
          />
        </Field>
        <div className="text-[12px] text-ink-500">Forecast horizon: 96</div>
      </Group>

      <Group title="View">
        <Tabs<ViewMode>
          value={s.view}
          onChange={s.setView}
          options={[
            { value: 'forecast', label: 'Forecast' },
            { value: 'graph', label: 'Dynamic graph' },
            { value: 'attention', label: 'Attention' },
          ]}
          size="sm"
          wrap
        />
      </Group>

      {s.view === 'graph' && (
        <Group title="Graph artifact">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={s.playing ? 'subtle' : 'outline'}
              icon={s.playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              onClick={() => s.set('playing', !s.playing)}
            >
              {s.playing ? 'Pause' : 'Play'}
            </Button>
            <span className="data-num text-[12px] text-ink-400">window {s.windowIdx + 1}/{nWindows}</span>
          </div>
          <Slider
            label="Window"
            value={s.windowIdx}
            min={0}
            max={Math.max(0, nWindows - 1)}
            onChange={(windowIdx) => {
              s.set('windowIdx', windowIdx);
              s.log('Window slider', undefined, `window ${windowIdx + 1}`);
            }}
            format={(value) => `#${value + 1}`}
          />

          {s.graphLayout === 'matrix' && (
            <Field label="Stored graph stage">
              <Select<GraphSource>
                value={s.graphSource}
                onChange={(source) => s.set('graphSource', source)}
                options={[
                  { value: 'static', label: 'Stored static prior' },
                  { value: 'dynamic', label: 'Stored learned score' },
                  { value: 'sparse', label: 'Stored message-passing graph' },
                  { value: 'difference', label: 'Derived display: score − prior' },
                ]}
                ariaLabel="Stored graph stage"
              />
            </Field>
          )}

          {s.graphLayout === '3d-timeline' && (
            <>
              <Slider
                label="Display strongest retained edges"
                value={s.topkRatio}
                min={0.05}
                max={1}
                step={0.05}
                onChange={(ratio) => s.set('topkRatio', ratio)}
                format={(ratio) => `${Math.round(ratio * 100)}%`}
              />
              <Slider
                label="Display weight threshold"
                value={s.edgeThreshold}
                min={0}
                max={1}
                step={0.05}
                onChange={(threshold) => s.set('edgeThreshold', threshold)}
                format={(threshold) => threshold.toFixed(2)}
              />
              <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[10px] leading-relaxed text-amber-900">
                Display only. These controls hide model-retained artifact edges by stored weight; they do not change the model mask, predictions, interventions, controls, or statistical results.
              </p>
            </>
          )}

          <Field label="Layout">
            <Tabs<GraphLayout>
              value={s.graphLayout}
              onChange={(layout) => s.set('graphLayout', layout)}
              options={[
                { value: 'matrix', label: 'Matrix' },
                { value: 'sidebyside', label: 'Side' },
                { value: '3d-timeline', label: '3D timeline' },
              ]}
              size="sm"
              wrap
            />
          </Field>

          {s.graphLayout === '3d-timeline' && (
            <Slider
              label="3D layer spacing"
              value={s.graph3DSpacing}
              min={3.4}
              max={6.4}
              step={0.2}
              onChange={(spacing) => s.set('graph3DSpacing', spacing)}
              format={(spacing) => spacing.toFixed(1)}
            />
          )}
        </Group>
      )}

      {s.view === 'attention' && (
        <Group title="Stored attention">
          <Field label="Patch resolution">
            <Tabs<ScaleId>
              value={s.scale}
              onChange={(scale) => s.set('scale', scale)}
              options={[
                { value: 1, label: 'S1 · fine' },
                { value: 2, label: 'S2 · medium' },
                { value: 3, label: 'S3 · coarse' },
              ]}
              size="sm"
              wrap
            />
          </Field>
          <Field label="Head">
            <Tabs<number>
              value={s.head}
              onChange={(head) => s.set('head', head)}
              options={[0, 1, 2, 3].map((head) => ({ value: head, label: `H${head}` }))}
              size="sm"
              wrap
            />
          </Field>
          <Toggle checked={s.showPatchBoundary} onChange={(value) => s.set('showPatchBoundary', value)} label="Show patch boundary" />
          <Toggle checked={s.linkAttention} onChange={(value) => s.set('linkAttention', value)} label="Link hover highlight to forecast" />
        </Group>
      )}

      <Group title="Utilities">
        <div className="grid grid-cols-2 gap-2">
          <Button size="sm" variant="outline" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => s.reset()}>Reset</Button>
          <Button
            size="sm"
            variant="outline"
            icon={<FileDown className="h-3.5 w-3.5" />}
            onClick={() => sample && download(`${sample.dataset}_display-state.json`, JSON.stringify(stateSnapshot(), null, 2), 'application/json')}
          >
            Export state
          </Button>
        </div>
      </Group>
    </div>
  );
}

function stateSnapshot() {
  const state = useDemoStore.getState();
  return {
    dataset: state.dataset,
    sampleId: state.sampleId,
    horizon: state.horizon,
    target: state.target,
    view: state.view,
    windowIdx: state.windowIdx,
    graphSource: state.graphSource,
    displayFilter: { strongestRetainedRatio: state.topkRatio, minimumStoredWeight: state.edgeThreshold },
    displayFilterAffectsModelResults: false,
    scale: state.scale,
    head: state.head,
    selectedEdge: state.selectedEdge,
    selectedNode: state.selectedNode,
  };
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return <div><div className="eyebrow mb-2">{title}</div><div className="space-y-2.5">{children}</div></div>;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div><div className="mb-1 text-[12px] text-ink-400">{label}</div>{children}</div>;
}
