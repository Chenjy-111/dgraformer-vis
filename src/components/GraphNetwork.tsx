import { useMemo } from 'react';
import type { GraphEdge, GraphLayout } from '@/types/demo';

interface Props {
  variables: string[];
  edges: GraphEdge[]; // already kept/filtered flagged
  layout: Exclude<GraphLayout, 'matrix' | 'sidebyside'>;
  showFiltered: boolean;
  showLabels: boolean;
  threshold: number;
  target: number;
  highlightTarget: boolean;
  selectedNode: number | null;
  selectedEdge: { source: number; target: number } | null;
  onHoverEdge?: (e: GraphEdge | null) => void;
  onClickEdge?: (e: GraphEdge) => void;
  onClickNode?: (n: number) => void;
  size?: number;
}

const SZ = 360;

export function GraphNetwork({
  variables,
  edges,
  layout,
  showFiltered,
  showLabels,
  threshold,
  target,
  highlightTarget,
  selectedNode,
  selectedEdge,
  onHoverEdge,
  onClickEdge,
  onClickNode,
  size = SZ,
}: Props) {
  const N = variables.length;
  const cx = size / 2;
  const cy = size / 2;
  const R = size / 2 - 38;

  const pos = useMemo(() => computeLayout(N, edges, layout, cx, cy, R), [N, edges, layout, cx, cy, R]);

  const visible = edges.filter((e) => e.weight >= threshold && (showFiltered || e.kept));
  // draw kept on top
  const ordered = [...visible].sort((a, b) => Number(a.kept) - Number(b.kept));

  const focusNode = selectedNode ?? (highlightTarget ? target : null);

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full">
      {ordered.map((e, i) => {
        const a = pos[e.source];
        const b = pos[e.target];
        const isFocus = focusNode != null && (e.source === focusNode || e.target === focusNode);
        const isSel = selectedEdge && selectedEdge.source === e.source && selectedEdge.target === e.target;
        const dim = focusNode != null && !isFocus;
        return (
          <line
            key={i}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke={e.kept ? '#1C7C7A' : '#C2C9D6'}
            strokeWidth={e.kept ? 0.8 + e.weight * 2.6 : 1}
            strokeDasharray={e.kept ? undefined : '3 3'}
            strokeOpacity={isSel ? 1 : dim ? 0.12 : e.kept ? 0.8 : 0.5}
            className="cursor-pointer"
            onMouseEnter={() => onHoverEdge?.(e)}
            onMouseLeave={() => onHoverEdge?.(null)}
            onClick={() => onClickEdge?.(e)}
          />
        );
      })}

      {pos.map((p, i) => {
        const isTarget = i === target;
        const isSel = i === selectedNode;
        const isFocus = focusNode === i;
        return (
          <g key={i} className="cursor-pointer" onClick={() => onClickNode?.(i)}>
            <circle
              cx={p.x}
              cy={p.y}
              r={isTarget ? 9 : 6.5}
              fill={isTarget ? '#D6453B' : isSel || isFocus ? '#4858A8' : '#7C8AA3'}
              stroke="#fff"
              strokeWidth={1.6}
            />
            {showLabels !== false && (
              <text
                x={p.x}
                y={p.y - 11}
                textAnchor="middle"
                fontSize={9.5}
                className={isTarget ? 'fill-pred font-semibold' : 'fill-ink-700'}
              >
                {variables[i]}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function computeLayout(
  N: number,
  edges: GraphEdge[],
  layout: 'circular' | 'force',
  cx: number,
  cy: number,
  R: number
): { x: number; y: number }[] {
  if (layout === 'circular') {
    return Array.from({ length: N }, (_, i) => {
      const ang = (i / N) * Math.PI * 2 - Math.PI / 2;
      return { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
    });
  }
  // deterministic spring layout
  const rnd = mulberry32(N * 99991 + 7);
  const p = Array.from({ length: N }, (_, i) => {
    const ang = (i / N) * Math.PI * 2;
    return { x: cx + Math.cos(ang) * R * 0.6 + (rnd() - 0.5) * 10, y: cy + Math.sin(ang) * R * 0.6 + (rnd() - 0.5) * 10 };
  });
  const kept = edges.filter((e) => e.kept);
  for (let iter = 0; iter < 120; iter++) {
    const disp = p.map(() => ({ x: 0, y: 0 }));
    // repulsion
    for (let i = 0; i < N; i++)
      for (let j = i + 1; j < N; j++) {
        let dx = p[i].x - p[j].x;
        let dy = p[i].y - p[j].y;
        let d2 = dx * dx + dy * dy + 0.01;
        const f = 5200 / d2;
        dx *= f;
        dy *= f;
        disp[i].x += dx;
        disp[i].y += dy;
        disp[j].x -= dx;
        disp[j].y -= dy;
      }
    // attraction along kept edges
    for (const e of kept) {
      let dx = p[e.source].x - p[e.target].x;
      let dy = p[e.source].y - p[e.target].y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const f = (d - 70) * 0.02 * (0.5 + e.weight);
      dx = (dx / d) * f;
      dy = (dy / d) * f;
      disp[e.source].x -= dx;
      disp[e.source].y -= dy;
      disp[e.target].x += dx;
      disp[e.target].y += dy;
    }
    for (let i = 0; i < N; i++) {
      p[i].x += Math.max(-6, Math.min(6, disp[i].x));
      p[i].y += Math.max(-6, Math.min(6, disp[i].y));
      // keep in bounds
      p[i].x = Math.max(cx - R, Math.min(cx + R, p[i].x));
      p[i].y = Math.max(cy - R, Math.min(cy + R, p[i].y));
    }
  }
  return p;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
