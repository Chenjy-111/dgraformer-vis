import { useEffect, useMemo } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
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
        buildNodeExplanation(
          { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head },
          s.target
        )
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample, s.windowIdx, s.graphSource, s.target, s.depth]);

  const priorC = useMemo(() => (sample?.history ? computePriorC(sample.history) : null), [sample]);

  if (!sample || !win) return null;
  const ctx = { sample, windowIdx: s.windowIdx, target: s.target, depth: s.depth, scale: s.scale, head: s.head };
  const isSide = s.graphLayout === 'sidebyside';
  const is3D = s.graphLayout === '3d-timeline';
  const isMSGNet = s.model === 'MSGNet';
  const scaleMeta = sample.msgnetContexts?.[s.windowIdx];
  const scaleEdges = sample.msgnetEdgeImpacts?.filter((edge) => edge.scaleIndex === s.windowIdx)
    .sort((a,b)=>b.predictionDeltaAbs-a.predictionDeltaAbs) ?? [];
  const selectedImpact = scaleEdges.find((edge)=>edge.source===s.selectedEdge?.source&&edge.target===s.selectedEdge?.target) ?? scaleEdges[0];
  const displayedSource = is3D ? 'sparse' : s.graphSource;
  const timelineEdges = useMemo(() => sample.windows.map((window) => {
    if (is3D) return recomputeTopK(window.edges, s.topkRatio, s.edgeThreshold);
    if (s.graphSource === 'static') return edgesFromMatrix(priorC ?? window.static_graph, 1);
    if (s.graphSource === 'dynamic') return recomputeTopK(window.edges, 1);
    if (s.graphSource === 'sparse') return edgesFromMatrix(window.sparse_graph, 1);
    return edgesFromMatrix(activeMatrix(window, 'difference', priorC ?? undefined), 1);
  }), [sample, s.graphSource, s.topkRatio, s.edgeThreshold, priorC, is3D]);
  const dynamicTimelineEdges = useMemo(
    () => sample.windows.map((window) => recomputeTopK(window.edges, s.topkRatio, s.edgeThreshold)),
    [sample, s.topkRatio, s.edgeThreshold]
  );

  return (
    <div className={is3D ? 'h-full' : ''}>
      <div className={is3D ? `pointer-events-none absolute left-[330px] top-7 z-20 flex items-baseline justify-between transition-all ${s.inspectorCollapsed ? 'right-12' : 'right-[370px]'}` : 'mb-3 flex items-baseline justify-between'}>
        <h3 className="text-[15px] font-semibold">
          {isMSGNet ? `Scale-conditioned adaptive graph · period ${scaleMeta?.period ?? '—'}` : `${isSide ? 'Dynamic vs sparse graph' : sourceLabel(displayedSource)} · window ${s.windowIdx + 1}/${sample.windows.length}`}
        </h3>
        <span className="data-num text-[12px] text-ink-400">
          {isMSGNet ? `scale ${s.windowIdx + 1}/${sample.windows.length} · contribution ${(scaleMeta?.contribution ?? 0).toExponential(2)}` : `steps ${win.start}–${win.end} · kept ${win.kept_edges.length}/${win.edges.length}`}
        </span>
      </div>

      {isMSGNet ? <>
        <div className="flex max-w-full justify-center overflow-auto pb-2"><GraphMatrix variables={sample.variables} matrix={win.sparse_graph} target={s.target} size={420}/></div>
        <div className="mt-5 border-t border-line pt-4"><div className="mb-3 flex items-center justify-between"><div><div className="eyebrow">Edge impact · real checkpoint forward</div><h4 className="mt-1 text-sm font-semibold">Select a directed edge in this scale</h4></div><span className="text-[11px] text-ink-400">42 non-self edges</span></div>
          <select className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm" value={selectedImpact?`${selectedImpact.source}-${selectedImpact.target}`:''} onChange={(e)=>{const [source,target]=e.target.value.split('-').map(Number);s.set('selectedEdge',{source,target});s.log('Select MSGNet edge',undefined,`${sample.variables[source]} → ${sample.variables[target]}`)}}>{scaleEdges.map(edge=><option key={`${edge.source}-${edge.target}`} value={`${edge.source}-${edge.target}`}>{sample.variables[edge.source]} → {sample.variables[edge.target]}</option>)}</select>
          {selectedImpact&&<div className="mt-3 grid gap-2 sm:grid-cols-4"><Metric label="Graph weight" value={selectedImpact.graphWeight.toFixed(4)}/><Metric label="Prediction Δ" value={selectedImpact.predictionDeltaAbs.toFixed(5)}/><Metric label="Control mean" value={selectedImpact.controlMean.toFixed(5)}/><Metric label="BH adjusted p" value={selectedImpact.bhAdjustedP.toFixed(3)}/></div>}
          {selectedImpact&&<p className="mt-3 text-[12px] leading-relaxed text-ink-500">Removing {sample.variables[selectedImpact.source]} → {sample.variables[selectedImpact.target]} changed MAE by {selectedImpact.errorDeltaMae>=0?'+':''}{selectedImpact.errorDeltaMae.toFixed(5)} and ranked at the {selectedImpact.controlPercentile.toFixed(1)}th percentile among same-sample, same-scale controls. This observed response did not obtain BH-adjusted support.</p>}
        </div>
      </> : is3D ? (
        <DynamicGraph3D
          variables={sample.variables}
          windows={timelineEdges}
          dynamicWindows={dynamicTimelineEdges}
          keepRatio={s.topkRatio}
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
          onClearSelection={(index) => {
            s.set('windowIdx', index);
            s.set('selectedNode', null);
            s.set('selectedEdge', null);
            s.log('Clear 3D selection', undefined, `window ${index + 1}`);
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
          <Panel caption="Sparse model graph Ẽw (w_ratio = 0.5)">
            <GraphMatrix variables={sample.variables} matrix={win.dynamic_graph} target={s.target} />
          </Panel>
        </div>
      ) : (
        <div className="flex max-w-full justify-center overflow-auto pb-2">
          <GraphMatrix
            variables={sample.variables}
            matrix={activeMatrix(win, s.graphSource, priorC ?? undefined)}
            diverging={s.graphSource === 'difference'}
            target={s.target}
            size={
              sample.variables.length > 12
                ? Math.min(720, 80 + sample.variables.length * 30)
                : Math.min(420, 60 + sample.variables.length * 44)
            }
          />
        </div>
      )}

      {!is3D && <p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">
        {s.graphSource === 'difference'
          ? 'Difference view: red cells are stronger in the dynamic graph than the prior, blue cells weaker — i.e. what this window learned beyond C.'
          : 'Hover a node to highlight its edges; click a node for its role, or an edge for why it was kept or filtered. Use the window slider to watch the graph evolve.'}
      </p>}
    </div>
  );
}

function Metric({label,value}:{label:string;value:string}){return <div className="rounded-lg bg-paper p-3"><div className="text-[9px] uppercase tracking-wide text-ink-400">{label}</div><div className="mt-1 font-mono text-sm font-semibold">{value}</div></div>}

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
