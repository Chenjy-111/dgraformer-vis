import { useEffect, useMemo } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { GraphNetwork } from './charts/GraphNetwork';
import { recomputeTopK } from '@/engine/graphAnalysis';
import { buildEdgeExplanation, buildWindowExplanation } from '@/engine/explanationEngine';
import type { GraphEdge } from '@/types/demo';
import { Badge } from './ui/Badge';

export function TopKFocusingView() {
  const s = useDemoStore();
  const sample = s.sample;
  const win = sample?.windows[s.windowIdx];

  useEffect(() => {
    if (sample)
      s.setExplanation(
        buildWindowExplanation({ sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head })
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample?.sample_id, s.windowIdx]);

  const edges = useMemo(() => (win ? recomputeTopK(win.edges, s.topkRatio) : []), [win, s.topkRatio]);
  if (!sample || !win) return null;

  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const kept = edges.filter((e) => e.kept);
  const filtered = edges.filter((e) => !e.kept);
  const targetFilter = (e: GraphEdge) =>
    !s.highlightTarget || e.source === s.target || e.target === s.target;
  const sparsity = Math.round((filtered.length / edges.length) * 100);

  const onEdge = (e: GraphEdge) => {
    s.set('selectedEdge', { source: e.source, target: e.target });
    s.log('Click edge (Top-K)', undefined, `${sample.variables[e.source]} → ${sample.variables[e.target]} (${e.kept ? 'kept' : 'filtered'})`);
    s.setExplanation(buildEdgeExplanation(ctx, e));
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-[15px] font-semibold">Essential correlation focusing · window {s.windowIdx + 1}</h3>
        <div className="flex items-center gap-3 text-[12px] text-ink-400">
          <span className="data-num">edges {edges.length}</span>
          <span className="data-num text-kept">kept {kept.length}</span>
          <span className="data-num text-ink-500">filtered {filtered.length}</span>
          <span className="data-num">sparsity {sparsity}%</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <BeforeAfter label="Before · Ew (original graph)">
          <GraphNetwork
            variables={sample.variables}
            edges={edges}
            layout="circular"
            showFiltered
            showLabels={false}
            threshold={0}
            target={s.target}
            highlightTarget={s.highlightTarget}
            selectedNode={null}
            selectedEdge={s.selectedEdge}
            onClickEdge={onEdge}
            size={300}
          />
        </BeforeAfter>
        <BeforeAfter label="After · Ẽw = Mw ⊙ Ew (sparsified)">
          <GraphNetwork
            variables={sample.variables}
            edges={kept}
            layout="circular"
            showFiltered={false}
            showLabels={false}
            threshold={0}
            target={s.target}
            highlightTarget={s.highlightTarget}
            selectedNode={null}
            selectedEdge={s.selectedEdge}
            onClickEdge={onEdge}
            size={300}
          />
        </BeforeAfter>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <EdgeList
          title="Kept edges (essential)"
          tone="kept"
          edges={kept.filter(targetFilter).slice(0, 8)}
          variables={sample.variables}
          onPick={onEdge}
          selected={s.selectedEdge}
        />
        <EdgeList
          title="Filtered edges (noise)"
          tone="filtered"
          edges={filtered.filter(targetFilter).slice(0, 8)}
          variables={sample.variables}
          onPick={onEdge}
          selected={s.selectedEdge}
        />
      </div>

      <p className="mt-4 text-[12.5px] leading-relaxed text-ink-400">
        Lowering the Top-K ratio keeps fewer, stronger edges. Click any edge to see why it survives focusing
        (essential correlation) or is removed (weak/spurious — likely noise during message passing).
        {s.highlightTarget && ' Lists are filtered to edges touching the selected target.'}
      </p>
    </div>
  );
}

function BeforeAfter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="eyebrow mb-2 text-center">{label}</div>
      <div className="flex justify-center">{children}</div>
    </div>
  );
}

function EdgeList({
  title,
  tone,
  edges,
  variables,
  onPick,
  selected,
}: {
  title: string;
  tone: 'kept' | 'filtered';
  edges: GraphEdge[];
  variables: string[];
  onPick: (e: GraphEdge) => void;
  selected: { source: number; target: number } | null;
}) {
  return (
    <div className="card p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[13px] font-semibold">{title}</span>
        <Badge tone={tone}>{edges.length}</Badge>
      </div>
      <ul className="space-y-1">
        {edges.length === 0 && <li className="px-2 py-3 text-center text-[12px] text-ink-400">No edges</li>}
        {edges.map((e) => {
          const sel = selected && selected.source === e.source && selected.target === e.target;
          return (
            <li key={`${e.source}-${e.target}`}>
              <button
                onClick={() => onPick(e)}
                className={`flex w-full items-center justify-between rounded-md border px-2.5 py-1.5 text-[12.5px] transition focus-visible:focus-ring ${
                  sel ? 'border-accent bg-accent-soft' : 'border-line bg-white hover:border-accent/50'
                }`}
              >
                <span className="font-mono">
                  {variables[e.source]} <span className="text-ink-400">→</span> {variables[e.target]}
                </span>
                <span className="data-num text-ink-400">
                  w {e.weight.toFixed(2)} · #{e.rank}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
