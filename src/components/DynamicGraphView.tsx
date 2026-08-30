import { useMemo } from 'react';
import { useDemoStore } from '@/store/useDemoStore';
import { GraphMatrix } from './charts/GraphMatrix';
import { activeMatrix } from '@/engine/graphAnalysis';
import { DynamicGraph3D } from './three/DynamicGraph3D';

export function DynamicGraphView() {
  const s = useDemoStore();
  const sample = s.sample;
  const win = sample?.windows[s.windowIdx];

  const retainedWindows = useMemo(
    () => sample?.windows.map((window) => window.kept_edges.map((edge) => ({ ...edge, kept: true }))) ?? [],
    [sample]
  );
  const modelWindows = useMemo(
    () => sample?.windows.map((window) => {
      const retained = new Set(window.kept_edges.map((edge) => `${edge.source}-${edge.target}`));
      return window.edges.map((edge) => ({ ...edge, kept: retained.has(`${edge.source}-${edge.target}`) }));
    }) ?? [],
    [sample]
  );

  if (!sample || !win) return null;

  const isSide = s.graphLayout === 'sidebyside';
  const is3D = s.graphLayout === '3d-timeline';
  const displayedSource = is3D ? 'sparse' : s.graphSource;

  return (
    <div className={is3D ? 'h-full' : ''}>
      <div className={is3D ? 'pointer-events-none absolute left-[330px] right-[370px] top-7 z-20 flex items-baseline justify-between' : 'mb-3 flex items-baseline justify-between'}>
        <h3 className="text-[15px] font-semibold">
          {isSide ? 'Learned score vs message-passing graph' : sourceLabel(displayedSource)} · window {s.windowIdx + 1}/{sample.windows.length}
        </h3>
        <span className="data-num text-[12px] text-ink-400">
          steps {win.start}–{win.end} · retained {win.kept_edges.length}/{win.edges.length}
        </span>
      </div>

      {is3D ? (
        <DynamicGraph3D
          variables={sample.variables}
          windows={retainedWindows}
          dynamicWindows={modelWindows}
          displayRatio={s.topkRatio}
          displayThreshold={s.edgeThreshold}
          activeWindow={s.windowIdx}
          target={s.target}
          spacing={s.graph3DSpacing}
          selectedNode={s.selectedNode}
          selectedEdge={s.selectedEdge}
          onSelectWindow={(index) => {
            s.set('windowIdx', index);
            s.log('Select artifact window', undefined, `window ${index + 1}`);
          }}
          onClearSelection={(index) => {
            s.set('windowIdx', index);
            s.set('selectedNode', null);
            s.set('selectedEdge', null);
            s.log('Clear graph selection', undefined, `window ${index + 1}`);
          }}
          onSelectNode={(node) => {
            s.set('selectedNode', node);
            s.set('selectedEdge', null);
            s.log('Select artifact node', undefined, sample.variables[node]);
          }}
          onSelectEdge={(edge, windowIdx) => {
            s.set('selectedEdge', { source: edge.source, target: edge.target });
            s.set('selectedNode', null);
            s.log('Select artifact edge', undefined, `${sample.variables[edge.source]} → ${sample.variables[edge.target]} · window ${windowIdx + 1}`);
          }}
        />
      ) : isSide ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel caption="Stored learned graph score">
            <GraphMatrix variables={sample.variables} matrix={win.dynamic_graph} target={s.target} />
          </Panel>
          <Panel caption="Stored message-passing graph">
            <GraphMatrix variables={sample.variables} matrix={win.sparse_graph} target={s.target} />
          </Panel>
        </div>
      ) : (
        <div className="flex max-w-full justify-center overflow-auto pb-2">
          <GraphMatrix
            variables={sample.variables}
            matrix={activeMatrix(win, s.graphSource)}
            diverging={s.graphSource === 'difference'}
            target={s.target}
            size={sample.variables.length > 12 ? Math.min(720, 80 + sample.variables.length * 30) : Math.min(420, 60 + sample.variables.length * 44)}
          />
        </div>
      )}

      {!is3D && (
        <p className="mt-3 text-[12.5px] leading-relaxed text-ink-400">
          {s.graphSource === 'difference'
            ? 'Descriptive display only: each cell is the stored learned-graph value minus the stored static-prior value. No new model result is computed.'
            : 'All matrices and retained-edge states are read from checkpoint-replayed artifacts. Selecting a relation defines a candidate for intervention validation; graph weight alone is not functional evidence.'}
        </p>
      )}
    </div>
  );
}

function Panel({ caption, children }: { caption: string; children: React.ReactNode }) {
  return <div><div className="eyebrow mb-2 text-center">{caption}</div><div className="flex justify-center">{children}</div></div>;
}

function sourceLabel(src: string): string {
  switch (src) {
    case 'static': return 'Stored static prior';
    case 'sparse': return 'Stored message-passing graph';
    case 'difference': return 'Derived display: learned score − static prior';
    default: return 'Stored learned graph score';
  }
}
