import type { GraphEdge } from '@/types/demo';

export function GraphNetwork({
  variables,
  edges,
  layout,
  showLabels,
  threshold,
  target,
  highlightTarget,
  selectedNode,
  selectedEdge,
  onClickEdge,
  onClickNode,
  size = 300,
  weightRange,
}: {
  variables: string[];
  edges: GraphEdge[];
  layout: 'circular' | 'force';
  showLabels: boolean;
  threshold: number;
  target: number;
  highlightTarget: boolean;
  selectedNode: number | null;
  selectedEdge: { source: number; target: number } | null;
  onClickEdge?: (e: GraphEdge) => void;
  onClickNode?: (n: number) => void;
  size?: number;
  weightRange?: [number, number];
}) {
  const N = variables.length;
  const radius = size / 2 - 30;
  const cx = size / 2;
  const cy = size / 2;

  const kept = edges.filter((e) => e.kept);
  const visible = kept.filter((e) => e.weight >= threshold);

  function nodePos(i: number) {
    const angle = (2 * Math.PI * i) / N - Math.PI / 2;
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  }

  const focused = highlightTarget ? target : null;
  const hasFocus = focused !== null;

  const targetColor = '#c85031';
  const selectColor = '#2563eb';
  const normalColor = '#94a3b8';

  const wMin = weightRange ? weightRange[0] : visible.length > 0 ? visible.reduce((a, e) => Math.min(a, e.weight), Infinity) : 0;
  const wMax = weightRange ? weightRange[1] : visible.length > 0 ? visible.reduce((a, e) => Math.max(a, e.weight), -Infinity) : 1;
  const wSpread = wMax - wMin || 0.01;

  function norm(w: number): number {
    // Map weight to 0..1 within observed range, with power curve to stretch low end
    const raw = (w - wMin) / wSpread;
    return Math.pow(Math.max(0, Math.min(1, raw)), 0.35);
  }

  /** RGB linear interpolation clamped to [0,1]. */
  function lerpColor(a: string, b: string, t: number): string {
    const ah = parseInt(a.slice(1), 16);
    const bh = parseInt(b.slice(1), 16);
    const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
    const r = clamp(((ah >> 16) & 0xff) * (1 - t) + ((bh >> 16) & 0xff) * t);
    const g = clamp(((ah >> 8) & 0xff) * (1 - t) + ((bh >> 8) & 0xff) * t);
    const bl = clamp((ah & 0xff) * (1 - t) + (bh & 0xff) * t);
    return `rgb(${r},${g},${bl})`;
  }

  /** Target-edge: yellow → vivid orange → dark red, stretched to observed range. */
  function targetEdgeColor(w: number): string {
    const t = norm(w);
    if (t <= 0.5) return lerpColor('#fbbf24', '#ea580c', t / 0.5);
    return lerpColor('#ea580c', '#7f1d1d', (t - 0.5) / 0.5);
  }

  /** Normal edge: very light → very dark slate, stretched to observed range. */
  function normalEdgeColor(w: number): string {
    return lerpColor('#e2e8f0', '#1e293b', norm(w));
  }

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Edges */}
      {visible.map((e) => {
        const s = nodePos(e.source);
        const t = nodePos(e.target);
        const isSel =
          selectedEdge?.source === e.source && selectedEdge?.target === e.target;
        const isTargetEdge =
          hasFocus && (e.source === focused || e.target === focused);

        const tNorm = norm(e.weight);

        let stroke: string;
        let opacity: number;
        let strokeW: number;

        if (isSel) {
          stroke = selectColor;
          opacity = 1;
          strokeW = 1.5 + tNorm * 2.5;
        } else if (isTargetEdge) {
          stroke = targetEdgeColor(e.weight);
          opacity = 0.9;
          strokeW = 0.8 + tNorm * 3.0;
        } else {
          stroke = normalEdgeColor(e.weight);
          opacity = hasFocus ? 0.25 : 0.45;
          strokeW = 0.8 + tNorm * 2.5;
        }

        return (
          <g key={`${e.source}-${e.target}`}>
            <line
              x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              stroke={stroke}
              strokeWidth={strokeW}
              opacity={opacity}
              className={onClickEdge ? 'cursor-pointer' : ''}
              onClick={() => onClickEdge?.(e)}
            />
            {showLabels && (
              <text
                x={(s.x + t.x) / 2}
                y={(s.y + t.y) / 2}
                fontSize={8}
                fill="#64748b"
                textAnchor="middle"
                opacity={hasFocus && !isTargetEdge ? 0.25 : 0.65}
              >
                {e.weight.toFixed(2)}
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {variables.map((v, i) => {
        const p = nodePos(i);
        const isTarget = i === target;
        const isSelected = i === selectedNode;

        let fill: string;
        if (isSelected) fill = selectColor;
        else if (isTarget) fill = targetColor;
        else fill = normalColor;

        return (
          <g key={v}>
            <circle
              cx={p.x} cy={p.y} r={6.5}
              fill={fill}
              stroke={isTarget || isSelected ? '#fff' : 'none'}
              strokeWidth={1.6}
              className={onClickNode ? 'cursor-pointer' : ''}
              onClick={() => onClickNode?.(i)}
            />
            <text
              x={p.x} y={p.y + 16}
              fontSize={9}
              fill={isTarget ? targetColor : '#475569'}
              textAnchor="middle"
              fontWeight={isTarget ? 600 : 400}
            >
              {v.length > 8 ? v.slice(0, 7) + '…' : v}
            </text>
          </g>
        );
      })}

      {/* Pulsating ring — rendered after all nodes so it stays on top */}
      {highlightTarget && (
        <circle
          cx={nodePos(target).x}
          cy={nodePos(target).y}
          r={5.5}
          fill="none"
          stroke={targetColor}
          strokeWidth={2}
        >
          <animate attributeName="r" values="5.5;9.5;5.5" dur="2s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.5;0.1;0.5" dur="2s" repeatCount="indefinite" />
        </circle>
      )}
    </svg>
  );
}
