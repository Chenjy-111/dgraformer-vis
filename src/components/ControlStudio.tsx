import { useEffect, type ReactNode } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { DATASETS, SAMPLE_DATASET_IDS } from '@/data/datasets';
import { HORIZONS } from '@/data/paperMetrics';
import { Select } from './ui/Select';
import { Slider } from './ui/Slider';
import { Toggle } from './ui/Toggle';
import { Tabs } from './ui/Tabs';
import { Button } from './ui/Button';
import { explanationToMarkdown, download, copyText } from '@/engine/narrativeGenerator';
import type {
  BaselineId,
  DatasetId,
  GraphLayout,
  GraphSource,
  Horizon,
  ScaleId,
  ViewMode,
} from '@/types/demo';
import { Pause, Play, RotateCcw, Pin, FileDown, Copy, Compass } from 'lucide-react';

const BASELINES: BaselineId[] = ['iTransformer', 'MSGNet', 'PatchTST', 'TimesNet', 'DLinear', 'Crossformer'];

export function ControlStudio() {
  const s = useDemoStore();
  const sample = s.sample;
  const nWindows = sample?.windows.length ?? 1;

  // window evolution playback
  useEffect(() => {
    if (!s.playing) return;
    const id = setInterval(() => {
      const st = useDemoStore.getState();
      const next = (st.windowIdx + 1) % (st.sample?.windows.length ?? 1);
      st.set('windowIdx', next);
    }, 1100);
    return () => clearInterval(id);
  }, [s.playing]);

  const variableOptions =
    sample?.variables.map((v, i) => ({ value: i, label: v })) ??
    DATASETS[s.dataset].variables.map((v, i) => ({ value: i, label: v }));

  return (
    <div className="space-y-5">
      <Group title="Case">
        <Field label="Dataset">
          <Select<DatasetId>
            value={s.dataset}
            onChange={(d) => s.setCase({ dataset: d })}
            options={SAMPLE_DATASET_IDS.map((d) => ({ value: d, label: `${d} · ${DATASETS[d].variables.length} vars` }))}
            ariaLabel="Dataset"
          />
        </Field>
        <Field label="Target variable">
          <Select<number>
            value={s.target}
            onChange={(n) => {
              s.set('target', n);
              s.log('Change target', undefined, sample?.variables[n]);
            }}
            options={variableOptions}
            ariaLabel="Target variable"
          />
        </Field>
        <Field label="Prediction horizon">
          <Tabs<Horizon>
            value={s.horizon}
            onChange={(h) => s.setCase({ horizon: h })}
            options={HORIZONS.filter((h) => h === 96).map((h) => ({ value: h, label: String(h) }))}
            size="sm"
            wrap
          />
        </Field>
      </Group>

      <Group title="View">
        <Tabs<ViewMode>
          value={s.view}
          onChange={(v) => s.setView(v)}
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
        <Group title="Graph">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={s.playing ? 'subtle' : 'outline'}
              icon={s.playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
              onClick={() => s.set('playing', !s.playing)}
            >
              {s.playing ? 'Pause' : 'Play'}
            </Button>
            <span className="data-num text-[12px] text-ink-400">
              window {s.windowIdx + 1}/{nWindows}
            </span>
          </div>
          <Slider
            label="Window"
            value={s.windowIdx}
            min={0}
            max={Math.max(0, nWindows - 1)}
            onChange={(v) => {
              s.set('windowIdx', v);
              s.log('Window slider', undefined, `window ${v + 1}`);
            }}
            format={(v) => `#${v + 1}`}
          />
          {s.graphLayout === 'matrix' && (
            <Field label="Graph source">
              <Select<GraphSource>
                value={s.graphSource}
                onChange={(g) => s.set('graphSource', g)}
                options={[
                  { value: 'static', label: 'Static prior C' },
                  { value: 'dynamic', label: 'Window dynamic Ew' },
                  { value: 'sparse', label: 'Sparse essential Ẽw' },
                  { value: 'difference', label: 'Difference (Ew − C)' },
                ]}
                ariaLabel="Graph source"
              />
            </Field>
          )}
          {s.graphLayout === '3d-timeline' ? (
            <>
              <Slider
                label="Top-K keep ratio"
                value={s.topkRatio}
                min={0.05}
                max={1}
                step={0.05}
                onChange={(v) => s.set('topkRatio', v)}
                format={(v) => `${Math.round(v * 100)}%`}
              />
              <Slider
                label="Edge threshold"
                value={s.edgeThreshold}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => s.set('edgeThreshold', v)}
                format={(v) => v.toFixed(2)}
              />
            </>
          ) : (
            <div className="rounded-lg border border-line bg-paper px-3 py-2 text-[11.5px] leading-relaxed text-ink-400">
              Model-fixed focusing: Top-K 50% <span aria-hidden="true">·</span> edge threshold 0
            </div>
          )}
          {s.view === 'graph' && (
            <Field label="Layout">
              <Tabs<GraphLayout>
                value={s.graphLayout}
                onChange={(l) => s.set('graphLayout', l)}
                options={[
                  { value: 'matrix', label: 'Matrix' },
                  { value: 'sidebyside', label: 'Side' },
                  { value: '3d-timeline', label: '3D timeline' },
                ]}
                size="sm"
                wrap
              />
            </Field>
          )}
          {s.view === 'graph' && s.graphLayout === '3d-timeline' && (
            <Slider
              label="3D layer spacing"
              value={s.graph3DSpacing}
              min={3.4}
              max={6.4}
              step={0.2}
              onChange={(v) => s.set('graph3DSpacing', v)}
              format={(v) => v.toFixed(1)}
            />
          )}
        </Group>
      )}

      {s.view === 'attention' && (
        <Group title="Attention">
          <Field label="Scale">
            <Tabs<ScaleId>
              value={s.scale}
              onChange={(v) => s.set('scale', v)}
              options={[
                { value: 1, label: 'S1 · local' },
                { value: 2, label: 'S2 · periodic' },
                { value: 3, label: 'S3 · trend' },
              ]}
              size="sm"
              wrap
            />
          </Field>
          <Field label="Head">
            <Tabs<number>
              value={s.head}
              onChange={(v) => s.set('head', v)}
              options={[0, 1, 2, 3].map((h) => ({ value: h, label: `H${h}` }))}
              size="sm"
              wrap
            />
          </Field>
          <Toggle checked={s.showPatchBoundary} onChange={(v) => s.set('showPatchBoundary', v)} label="Show patch boundary" />
          <Toggle checked={s.linkAttention} onChange={(v) => s.set('linkAttention', v)} label="Link attention to forecast" />
        </Group>
      )}

      <Group title="Explanation detail">
        <Toggle checked={s.showFormulas} onChange={(v) => s.set('showFormulas', v)} label="Show formulas" />
        <Toggle checked={s.showAssumptions} onChange={(v) => s.set('showAssumptions', v)} label="Show assumptions" />
        <Toggle checked={s.showCaveats} onChange={(v) => s.set('showCaveats', v)} label="Show caveats" />
        <Toggle checked={s.showEvidence} onChange={(v) => s.set('showEvidence', v)} label="Show evidence cards" />
      </Group>

      <Group title="Comparison">
        <Field label="Baseline">
          <Select<BaselineId>
            value={s.compareBaseline}
            onChange={(b) => s.set('compareBaseline', b)}
            options={BASELINES.map((b) => ({ value: b, label: b }))}
            ariaLabel="Baseline"
          />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Slider
            label="Window A"
            value={s.compareWindowA}
            min={0}
            max={Math.max(0, nWindows - 1)}
            onChange={(v) => s.set('compareWindowA', v)}
            format={(v) => `#${v + 1}`}
          />
          <Slider
            label="Window B"
            value={s.compareWindowB}
            min={0}
            max={Math.max(0, nWindows - 1)}
            onChange={(v) => s.set('compareWindowB', v)}
            format={(v) => `#${v + 1}`}
          />
        </div>
      </Group>

      <Group title="Utilities">
        <div className="grid grid-cols-2 gap-2">
          <Button size="sm" variant="outline" icon={<Pin className="h-3.5 w-3.5" />} onClick={() => s.explanation && s.pin(s.explanation)}>
            Pin
          </Button>
          <Button size="sm" variant="outline" icon={<RotateCcw className="h-3.5 w-3.5" />} onClick={() => { s.reset(); s.log('Reset view'); }}>
            Reset
          </Button>
          <Button
            size="sm"
            variant="outline"
            icon={<FileDown className="h-3.5 w-3.5" />}
            onClick={() => sample && download(`${sample.dataset}_state.json`, JSON.stringify(stateSnapshot(), null, 2), 'application/json')}
          >
            Export JSON
          </Button>
          <Button size="sm" variant="outline" icon={<Copy className="h-3.5 w-3.5" />} onClick={() => s.explanation && copyText(explanationToMarkdown(s.explanation))}>
            Copy expl.
          </Button>
          <Button size="sm" variant="subtle" icon={<Compass className="h-3.5 w-3.5" />} onClick={() => s.startTour()}>
            Tour
          </Button>
        </div>
      </Group>
    </div>
  );
}

function stateSnapshot() {
  const s = useDemoStore.getState();
  return {
    dataset: s.dataset,
    sampleId: s.sampleId,
    horizon: s.horizon,
    target: s.target,
    view: s.view,
    windowIdx: s.windowIdx,
    graphSource: s.graphSource,
    topkRatio: s.topkRatio,
    scale: s.scale,
    head: s.head,
    depth: s.depth,
    selectedEdge: s.selectedEdge,
    selectedNode: s.selectedNode,
    selectedErrorStep: s.selectedErrorStep,
  };
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="eyebrow mb-2">{title}</div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1 text-[12px] text-ink-400">{label}</div>
      {children}
    </div>
  );
}
