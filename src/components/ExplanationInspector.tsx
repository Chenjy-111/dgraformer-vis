import { useDemoStore } from '@/store/useDemoStore';

export function ExplanationInspector() {
  const sample = useDemoStore((state) => state.sample);
  const windowIdx = useDemoStore((state) => state.windowIdx);
  const selectedEdge = useDemoStore((state) => state.selectedEdge);
  const selectedNode = useDemoStore((state) => state.selectedNode);
  const view = useDemoStore((state) => state.view);
  const win = sample?.windows[windowIdx];
  const edge = selectedEdge && win
    ? win.edges.find((candidate) => candidate.source === selectedEdge.source && candidate.target === selectedEdge.target)
    : undefined;
  const retained = Boolean(selectedEdge && win?.kept_edges.some((candidate) => candidate.source === selectedEdge.source && candidate.target === selectedEdge.target));

  return (
    <aside className="space-y-4">
      <div>
        <span className="eyebrow">Artifact inspector</span>
        <p className="mt-2 text-[11px] leading-relaxed text-ink-400">Read-only checkpoint fields.</p>
      </div>

      <section className="card p-4">
        <div className="eyebrow">Current context</div>
        <dl className="mt-3 space-y-2">
          <Row label="Model" value="DGraFormer" />
          <Row label="Dataset / sample" value={sample ? `${sample.dataset} / ${sample.sample_id}` : '—'} />
          <Row label="View" value={view} />
          <Row label="Graph window" value={sample ? `${windowIdx + 1} / ${sample.windows.length}` : '—'} />
          <Row label="Artifact run" value={sample?.provenance?.runId ? shortHash(sample.provenance.runId) : 'not included'} mono />
        </dl>
      </section>

      {edge && sample ? (
        <section className="card border-accent/30 p-4">
          <div className="eyebrow">Selected candidate relation</div>
          <h3 className="mt-2 text-[17px] font-semibold text-ink-900">
            {sample.variables[edge.source]} → {sample.variables[edge.target]}
          </h3>
          <dl className="mt-3 space-y-2">
            <Row label="Stored weight" value={edge.weight.toFixed(6)} mono />
            <Row label="Stored rank" value={`#${edge.rank}`} mono />
            <Row label="Model mask state" value={retained ? 'retained' : 'excluded'} />
            <Row label="Graph window" value={String(windowIdx + 1)} />
          </dl>
          <p className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[10.5px] leading-relaxed text-amber-900">
            Candidate only. Validate it with the intervention and matched controls.
          </p>
        </section>
      ) : selectedNode != null && sample ? (
        <section className="card p-4">
          <div className="eyebrow">Selected variable</div>
          <h3 className="mt-2 text-[17px] font-semibold">{sample.variables[selectedNode]}</h3>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-400">Selection is navigational; no role is inferred.</p>
        </section>
      ) : (
        <section className="card p-4 text-[12px] leading-relaxed text-ink-400">
          Select an edge to inspect and test it.
        </section>
      )}

      <section className="rounded-xl border border-line bg-white p-4 text-[10.5px] leading-relaxed text-ink-400">
        Precomputed artifacts only; the browser does not rerun the model.
      </section>
    </aside>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="flex items-start justify-between gap-3 border-b border-line/60 pb-2 last:border-0 last:pb-0"><dt className="text-[11px] text-ink-400">{label}</dt><dd className={`text-right text-[11px] text-ink-700 ${mono ? 'font-mono' : ''}`}>{value}</dd></div>;
}

function shortHash(value: string) {
  return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value;
}
