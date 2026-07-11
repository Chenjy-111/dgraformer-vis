import { useMemo, useRef, useState } from 'react';
import type { SampleData } from '@/types/demo';

interface Props {
  sample: SampleData;
  variable: number;
  windowIdx: number;
  showPatchBoundary: boolean;
  onPickStep?: (futureStep: number) => void;
  onPickWindow?: (windowIdx: number) => void;
  highlightPatches?: [number, number] | null; // [patchStart, patchEnd] in look-back steps
  selectedFutureStep?: number | null;
}

const W = 760;
const H = 300;
const PAD = { l: 44, r: 16, t: 18, b: 28 };

export function ForecastChart({ sample, variable, windowIdx, showPatchBoundary, onPickStep, onPickWindow, highlightPatches, selectedFutureStep }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ x: number; idx: number; future: boolean } | null>(null);

  const hist = sample.history[variable] ?? [];
  const truth = sample.ground_truth[variable] ?? [];
  const pred = sample.prediction[variable] ?? [];
  const T = hist.length;
  const Hor = truth.length;
  const N = T + Hor;

  const { yMin, yMax } = useMemo(() => {
    const all = [...hist, ...truth, ...pred];
    let lo = Math.min(...all);
    let hi = Math.max(...all);
    const pad = (hi - lo) * 0.08 || 0.1;
    return { yMin: lo - pad, yMax: hi + pad };
  }, [hist, truth, pred]);

  const plotW = W - PAD.l - PAD.r;
  const plotH = H - PAD.t - PAD.b;
  const xAt = (i: number) => PAD.l + (i / (N - 1)) * plotW;
  const yAt = (v: number) => PAD.t + (1 - (v - yMin) / (yMax - yMin)) * plotH;

  const line = (arr: number[], offset: number) =>
    arr.map((v, i) => `${i === 0 ? 'M' : 'L'}${xAt(i + offset).toFixed(1)},${yAt(v).toFixed(1)}`).join(' ');

  // error band (between truth and pred in future region)
  const band = useMemo(() => {
    const top = truth.map((v, i) => `${xAt(i + T).toFixed(1)},${yAt(v).toFixed(1)}`);
    const bot = pred.map((v, i) => `${xAt(i + T).toFixed(1)},${yAt(v).toFixed(1)}`).reverse();
    return `M${top.join(' L')} L${bot.join(' L')} Z`;
  }, [truth, pred, yMin, yMax]);

  const win = sample.windows[windowIdx];

  // y ticks
  const yticks = Array.from({ length: 5 }, (_, i) => yMin + (i / 4) * (yMax - yMin));

  function handleMove(e: React.MouseEvent) {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const idx = Math.round(((px - PAD.l) / plotW) * (N - 1));
    if (idx < 0 || idx >= N) return setHover(null);
    setHover({ x: xAt(idx), idx, future: idx >= T });
  }

  function handleClick() {
    if (!hover) return;
    if (hover.future) onPickStep?.(hover.idx - T);
    else {
      const wi = sample.windows.findIndex((w) => hover.idx >= w.start && hover.idx < w.end);
      onPickWindow?.(wi < 0 ? 0 : wi);
    }
  }

  const hv = hover
    ? {
        hist: hover.idx < T ? hist[hover.idx] : null,
        truth: hover.idx >= T ? truth[hover.idx - T] : null,
        pred: hover.idx >= T ? pred[hover.idx - T] : null,
        err: hover.idx >= T ? sample.error[variable]?.[hover.idx - T] : null,
      }
    : null;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full select-none"
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
        onClick={handleClick}
      >
        {/* prediction region background */}
        <rect x={xAt(T)} y={PAD.t} width={W - PAD.r - xAt(T)} height={plotH} fill="#F2F5FB" />
        <text x={xAt(T) + 6} y={PAD.t + 12} className="fill-ink-400" fontSize={10}>
          forecast region
        </text>

        {/* y grid + ticks */}
        {yticks.map((t, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={yAt(t)} y2={yAt(t)} stroke="#EDF0F5" />
            <text x={PAD.l - 6} y={yAt(t) + 3} textAnchor="end" fontSize={9} className="fill-ink-400 data-num">
              {t.toFixed(2)}
            </text>
          </g>
        ))}

        {/* look-back window overlays */}
        {sample.windows.map((w) => (
          <rect
            key={w.window_id}
            x={xAt(w.start)}
            y={PAD.t}
            width={xAt(w.end) - xAt(w.start)}
            height={plotH}
            fill={w.window_id === windowIdx ? 'rgba(72,88,168,0.08)' : 'transparent'}
            stroke={w.window_id === windowIdx ? 'rgba(72,88,168,0.4)' : '#E8EBF1'}
            strokeDasharray="3 3"
            className="cursor-pointer"
            onClick={(e) => {
              e.stopPropagation();
              onPickWindow?.(w.window_id);
            }}
          />
        ))}

        {/* patch boundaries (look-back) */}
        {showPatchBoundary &&
          Array.from({ length: Math.floor(T / sample.patchLen) + 1 }, (_, i) => i * sample.patchLen).map((s) => (
            <line key={s} x1={xAt(s)} x2={xAt(s)} y1={H - PAD.b} y2={H - PAD.b + 4} stroke="#C7CEDB" />
          ))}

        {/* highlighted patches (from attention link) */}
        {highlightPatches && (
          <rect
            x={xAt(highlightPatches[0])}
            y={PAD.t}
            width={xAt(highlightPatches[1]) - xAt(highlightPatches[0])}
            height={plotH}
            fill="rgba(168,52,31,0.10)"
            stroke="rgba(168,52,31,0.5)"
          />
        )}

        {/* divider at T */}
        <line x1={xAt(T)} x2={xAt(T)} y1={PAD.t} y2={H - PAD.b} stroke="#9AA4B5" strokeDasharray="2 3" />

        {/* error band */}
        <path d={band} fill="#FBE0E2" opacity={0.85} />

        {/* series */}
        <path d={line(hist, 0)} fill="none" stroke="#9AA4B5" strokeWidth={1.6} />
        <path d={line(truth, T)} fill="none" stroke="#2C5BD6" strokeWidth={1.8} />
        <path d={line(pred, T)} fill="none" stroke="#D6453B" strokeWidth={1.8} strokeDasharray="5 3" />

        {/* hover marker */}
        {selectedFutureStep != null && (
          <g>
            <line x1={xAt(T + selectedFutureStep)} x2={xAt(T + selectedFutureStep)} y1={PAD.t} y2={H - PAD.b} stroke="#D6453B" strokeWidth={1.2} />
            <circle cx={xAt(T + selectedFutureStep)} cy={yAt(pred[selectedFutureStep] ?? 0)} r={4} fill="#D6453B" stroke="white" strokeWidth={1.5} />
          </g>
        )}
        {hover && (
          <line x1={hover.x} x2={hover.x} y1={PAD.t} y2={H - PAD.b} stroke="#33415C" strokeWidth={0.8} opacity={0.5} />
        )}

        {/* x labels */}
        <text x={PAD.l} y={H - 8} fontSize={9} className="fill-ink-400 data-num">-{T}</text>
        <text x={xAt(T)} y={H - 8} fontSize={9} textAnchor="middle" className="fill-ink-400 data-num">0</text>
        <text x={W - PAD.r} y={H - 8} fontSize={9} textAnchor="end" className="fill-ink-400 data-num">+{Hor}</text>
      </svg>

      {/* legend */}
      <div className="mt-1 flex flex-wrap gap-3 px-1 text-[11px] text-ink-500">
        <Legend color="#9AA4B5" label="History" />
        <Legend color="#2C5BD6" label="Ground truth" />
        <Legend color="#D6453B" dashed label="Prediction" />
        <span className="inline-flex items-center gap-1"><span className="inline-block h-2 w-3 bg-errfill" /> Error</span>
      </div>

      {/* tooltip */}
      {hv && hover && (
        <div
          className="pointer-events-none absolute z-20 rounded-md border border-line bg-white px-2 py-1.5 text-[11px] shadow-pop"
          style={{ left: `${(hover.x / W) * 100}%`, top: 6, transform: 'translateX(8px)' }}
        >
          <div className="data-num text-ink-500">step {hover.future ? `+${hover.idx - T}` : hover.idx - T}</div>
          {hv.hist != null && <div>History: <span className="data-num">{hv.hist.toFixed(3)}</span></div>}
          {hv.truth != null && <div className="text-truth">Truth: <span className="data-num">{hv.truth.toFixed(3)}</span></div>}
          {hv.pred != null && <div className="text-pred">Pred: <span className="data-num">{hv.pred.toFixed(3)}</span></div>}
          {hv.err != null && <div className="text-pred">|err|: <span className="data-num">{hv.err.toFixed(3)}</span></div>}
        </div>
      )}
    </div>
  );
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1">
      <svg width={16} height={6}>
        <line x1={0} y1={3} x2={16} y2={3} stroke={color} strokeWidth={2} strokeDasharray={dashed ? '4 2' : undefined} />
      </svg>
      {label}
    </span>
  );
}
