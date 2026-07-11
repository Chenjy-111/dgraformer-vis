import { useEffect, useMemo } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { GraphNetwork } from './charts/GraphNetwork';
import { GraphMatrix } from './charts/GraphMatrix';
import { activeMatrix, computePriorC, recomputeTopK } from '@/engine/graphAnalysis';
import { buildEdgeExplanation, buildNodeExplanation, buildWindowExplanation } from '@/engine/explanationEngine';
import type { GraphEdge } from '@/types/demo';
import { DynamicGraph3D } from './three/DynamicGraph3D';

function edgesFromMatrix(m: number[][], keepRatio: number): GraphEdge[] {
  const N = m.length;
  const list: GraphEdge[] = [];
  for (let i = 0; i < N; i++)
    for (let j = 0; j < N; j++) {
      if (i === j) continue;
      list.push({ source: i, target: j, weight: m[i][j], rank: 0, kept: false });
    }
  list.sort((a, b) => b.weight - a.weight);
  const k = Math.max(1, Math.round(list.length * keepRatio));
  list.forEach((e, idx) => {
    e.rank = idx + 1;
    e.kept = idx < k;
  });
  return list;
}

export function DynamicGraphView() {
  const s = useDemoStore();
  const sample = s.sample;
  const win = sample?.windows[s.windowIdx];

  useEffect(() => {
    if (sample) {
      s.setExplanation(
        buildWindowExplanation({ sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head })
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample?.sample_id, s.windowIdx, s.graphSource]);

  const priorC = useMemo(() => (sample?.history ? computePriorC(sample.history) : null), [sample?.sample_id]);

  const networkEdges = useMemo(() => {
    if (!win) return [];
    if (s.graphSource === 'static') return edgesFromMatrix(priorC ?? win.static_graph, 1);
    if (s.graphSource === 'dynamic') return recomputeTopK(win.edges, 1);
    if (s.graphSource === 'sparse') return edgesFromMatrix(win.sparse_graph, 1);
    // difference
    return edgesFromMatrix(activeMatrix(win, 'difference', priorC ?? undefined), 1);
  }, [win, s.graphSource, priorC]);

  if (!sample || !win) return null;
  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const isMatrix = s.graphLayout === 'matrix';
  const isSide = s.graphLayout === 'sidebyside';
  const is3D = s.graphLayout === '3d-timeline';
  const netLayout = 'circular';
  const timelineEdges = useMemo(() => sample.windows.map((window) => {
    if (s.graphSource === 'static') return edgesFromMatrix(priorC ?? window.static_graph, 1);
    if (s.graphSource === 'dynamic') return recomputeTopK(window.edges, 1);
    if (s.graphSource === 'sparse') return edgesFromMatrix(window.sparse_graph, 1);
    return edgesFromMatrix(activeMatrix(window, 'difference', priorC ?? undefined), 1);
  }), [sample, s.graphSource, priorC]);

  return (
    <div className={is3D ? 'h-full' : ''}>
      <div className={is3D ? 'pointer-events-none absolute left-[330px] right-[370px] top-7 z-20 flex items-baseline justify-between' : 'mb-3 flex items-baseline justify-between'}>
        <h3 className="text-[15px] font-semibold">
          {sourceLabel(s.graphSource)} · window {s.windowIdx + 1}/{sample.windows.length}
        </h3>
        <span className="data-num text-[12px] text-ink-400">
          steps {win.start}–{win.end} · kept {win.kept_edges.length}/{win.edges.length}
        </span>
      </div>

      {is3D ? (
        <DynamicGraph3D
          variables={sample.variables}
          windows={timelineEdges}
          activeWindow={s.windowIdx}
          target={s.target}
          threshold={s.edgeThreshold}
          spacing={s.graph3DSpacing}
          selectedNode={s.selectedNode}
          selectedEdge={s.selectedEdge}
          onSelectWindow={(index) => {
            s.set('windowIdx', index);
            s.log('Select 3D window', undefined, `window ${index + 1}`);
            s.setExplanation(buildWindowExplanation({ sample, windowIdx: index, target: s.target, depth: s.depth, scale: s.scale, head: s.head }));
          }}
          onSelectNode={(node) => {
            const windowIdx = useDemoStore.getState().windowIdx;
            s.set('selectedNode', node);
            s.set('selectedEdge', null);
            s.log('Click 3D node', undefined, sample.variables[node]);
            s.setExplanation(buildNodeExplanation({ ...ctx, windowIdx }, node));
          }}
          onSelectEdge={(edge, windowIdx) => {
            s.set('selectedEdge', { source: edge.source, target: edge.target });
            s.set('selectedNode', null);
            s.log('Click 3D edge', undefined, `${sample.variables[edge.source]} → ${sample.variables[edge.target]}`);
            s.setExplanation(buildEdgeExplanation({ ...ctx, windowIdx }, edge));
          }}
        />
      ) : isSide ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel caption="Dynamic graph Ew (all weights)">
            <GraphMatrix variables={sample.variables} matrix={win.dynamic_graph} target={s.target} />
          </Panel>
          <Panel caption="Sparse graph Ẽw (Top-K)">
            <GraphMatrix variables={sample.variables} matrix={win.sparse_graph} target={s.target} />
          </Panel>
        </div>
      ) : isMatrix ? (
        <div className="flex justify-center">
          <GraphMatrix
            variables={sample.variables}
            matrix={activeMatrix(win, s.graphSource, priorC ?? undefined)}
            diverging={s.graphSource === 'difference'}
            target={s.target}
            size={Math.min(420, 60 + sample.variables.length * 44)}
          />
        </div>
      ) : (
        <div className="flex justify-center">
          <GraphNetwork
            variables={sample.variables}
            edges={networkEdges}
            layout={netLayout}
            showLabels={s.showEdgeLabels}
            threshold={s.edgeThreshold}
            target={s.target}
            highlightTarget={s.highlightTarget}
            selectedNode={s.selectedNode}
            selectedEdge={s.selectedEdge}
            onClickEdge={(e) => {
              s.set('selectedEdge', { source: e.source, target: e.target });
              s.set('selectedNode', null);
              s.log('Click edge', undefined, `${sample.variables[e.source]} → ${sample.variables[e.target]}`);
              s.setExplanation(buildEdgeExplanation(ctx, e));
            }}
            onClickNode={(n) => {
              s.set('selectedNode', n);
              s.set('selectedEdge', null);
              s.log('Click node', undefined, sample.variables[n]);
              s.setExplanation(buildNodeExplanation(ctx, n));
            }}
          />
        </div>
      )}

      <p className={is3D ? 'pointer-events-none absolute bottom-6 left-[330px] right-[370px] z-20 text-center text-[12px] leading-relaxed text-ink-400' : 'mt-3 text-[12.5px] leading-relaxed text-ink-400'}>
        {s.graphSource === 'difference'
          ? 'Difference view: red cells are stronger in the dynamic graph than the prior, blue cells weaker — i.e. what this window learned beyond C.'
          : 'Hover a node to highlight its edges; click a node for its role, or an edge for why it was kept or filtered. Use the window slider to watch the graph evolve.'}
      </p>
    </div>
  );
}

function Panel({ caption, children }: { caption: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="eyebrow mb-2 text-center">{caption}</div>
      <div className="flex justify-center">{children}</div>
    </div>
  );
}

function sourceLabel(src: string): string {
  switch (src) {
    case 'static':
      return 'Static prior C';
    case 'sparse':
      return 'Sparse essential graph Ẽw';
    case 'difference':
      return 'Difference (Ew − C)';
    default:
      return 'Window dynamic graph Ew';
  }
}
