import { useDemoStore } from '@/store/useDemoStore';
import { Badge } from './ui/Badge';
import { KatexSpan } from './KatexSpan';
import { Meter } from './ui/Meter';
import { Button } from './ui/Button';
import { Pin, Copy } from 'lucide-react';
import { explanationToMarkdown, copyText } from '@/engine/narrativeGenerator';
import type { EvidenceItem } from '@/types/explanation';

const MODE_LABEL: Record<string, string> = {
  forecast: 'Forecast',
  graph: 'Dynamic graph',
  topk: 'Top-K focusing',
  attention: 'Multi-scale attention',
  error: 'Error diagnosis',
  ablation: 'Ablation',
  sensitivity: 'Sensitivity',
  narrative: 'Narrative',
};

export function ExplanationInspector() {
  const s = useDemoStore();
  const e = s.explanation;
  const sample = s.sample;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Explanation inspector</span>
        {e && (
          <div className="flex gap-1.5">
            <button
              title="Copy as Markdown"
              onClick={() => copyText(explanationToMarkdown(e))}
              className="rounded-md border border-line p-1.5 text-ink-400 hover:text-accent focus-visible:focus-ring"
            >
              <Copy className="h-3.5 w-3.5" />
            </button>
            <button
              title="Pin explanation"
              onClick={() => s.pin(e)}
              className="rounded-md border border-line p-1.5 text-ink-400 hover:text-accent focus-visible:focus-ring"
            >
              <Pin className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* current selection state */}
      <div className="card p-3 text-[12px] text-ink-500">
        <div className="data-num">
          {sample ? `${sample.dataset} · sample ${sample.sample_id} · h${sample.horizon}` : '—'}
        </div>
        <div className="mt-1 flex flex-wrap gap-1.5">
          <Badge tone="accent">{MODE_LABEL[s.view]}</Badge>
          {sample && <Badge>target {sample.variables[s.target]}</Badge>}
          {(s.view === 'graph' || s.view === 'topk') && <Badge>win {s.windowIdx + 1}</Badge>}
          {s.view === 'attention' && <Badge>scale {s.scale} · H{s.head}</Badge>}
        </div>
      </div>

      {!e ? (
        <div className="card p-4 text-[13px] text-ink-400">
          Interact with the canvas — click an edge, node, patch, window or error step — and a structured explanation
          appears here.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="card p-4">
            <h3 className="font-serif text-[16px] font-semibold leading-snug text-ink-900">{e.title}</h3>
            <div className="mt-0.5 data-num text-[11px] text-ink-400">{e.selectionLabel}</div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-700">{e.summary}</p>
          </div>

          {s.showEvidence && e.evidence.length > 0 && (
            <div className="card p-3">
              <div className="eyebrow mb-2">Evidence</div>
              <div className="space-y-1">
                {e.evidence.map((ev, i) => (
                  <EvidenceRow key={i} item={ev} />
                ))}
              </div>
            </div>
          )}

          {s.showFormulas && e.formula && (
            <Note label="Formula">
              <KatexSpan html={e.formula} />
            </Note>
          )}
          {s.showAssumptions && e.assumption && <Note label="Assumption">{e.assumption}</Note>}
          {s.showCaveats && e.caveat && <Note label="Caveat" tone="warn">{e.caveat}</Note>}
          {e.nextStep && <Note label="Suggested next step" tone="accent">{e.nextStep}</Note>}

          <div className="card p-3">
            <div className="eyebrow mb-2">Explanation quality</div>
            <div className="space-y-2">
              <Meter label="Evidence coverage" value={e.quality.evidence} />
              <Meter label="Local specificity" value={e.quality.specificity} />
              <Meter label="Mechanism clarity" value={e.quality.mechanism} />
              <Meter label="Uncertainty awareness" value={e.quality.uncertainty} />
            </div>
          </div>

          {s.pinned.length > 0 && (
            <div className="card p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="eyebrow">Pinned ({s.pinned.length})</span>
                <Button size="sm" variant="ghost" onClick={() => s.pinned.forEach((p) => s.unpin(p.id))}>
                  clear
                </Button>
              </div>
              <ul className="space-y-1">
                {s.pinned.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-2 text-[12px]">
                    <span className="truncate text-ink-700">{p.title}</span>
                    <button onClick={() => s.unpin(p.id)} className="text-ink-400 hover:text-pred">
                      ✕
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceRow({ item }: { item: EvidenceItem }) {
  const tone =
    item.tone === 'kept'
      ? 'text-kept'
      : item.tone === 'filtered'
        ? 'text-ink-400'
        : item.tone === 'warn'
          ? 'text-pred'
          : 'text-ink-700';
  return (
    <div className="flex items-start justify-between gap-2 border-b border-line/60 pb-1 last:border-0">
      <span className="text-[12px] text-ink-400">{item.label}</span>
      <span className={`data-num text-[12px] text-right ${tone}`}>{item.value}</span>
    </div>
  );
}

function Note({
  label,
  children,
  mono,
  tone = 'neutral',
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
  tone?: 'neutral' | 'warn' | 'accent';
}) {
  const border =
    tone === 'warn' ? 'border-pred/30 bg-pred/5' : tone === 'accent' ? 'border-accent/30 bg-accent-soft' : 'border-line bg-white';
  return (
    <div className={`rounded-card border p-3 ${border}`}>
      <div className="eyebrow mb-1">{label}</div>
      <div className={`text-[12.5px] leading-relaxed text-ink-700 ${mono ? 'font-mono' : ''}`}>{children}</div>
    </div>
  );
}
