import type { GraphEdge, GraphLayout } from '@/types/demo';

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
  onClickEdge,
  onClickNode,
  size = 300,
}: {
  variables: string[];
  edges: GraphEdge[];
  layout: GraphLayout;
  showFiltered: boolean;
  showLabels: boolean;
  threshold: number;
  target: number;
  highlightTarget: boolean;
  selectedNode: number | null;
  selectedEdge: { source: number; target: number } | null;
  onClickEdge?: (e: GraphEdge) => void;
  onClickNode?: (n: number) => void;
  size?: number;
}) {
  const N = variables.length;
  const radius = size / 2 - 30;
  const cx = size / 2;
  const cy = size / 2;

  const filtered = edges.filter((e) => e.kept);

  function nodePos(i: number) {
    const angle = (2 * Math.PI * i) / N - Math.PI / 2;
    const r = layout === 'circular' ? radius : radius * (0.5 + 0.5 * Math.random());
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  }

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Edges */}
      {(showFiltered ? edges : filtered).map((e) => {
        if (e.weight < threshold) return null;
        const s = nodePos(e.source);
        const t = nodePos(e.target);
        const isSel =
          selectedEdge?.source === e.source && selectedEdge?.target === e.target;
        const isTargetRelated =
          highlightTarget && (e.source === target || e.target === target);
        const opacity = e.kept ? (isTargetRelated ? 0.9 : 0.5) : 0.12;
        const strokeW = e.kept ? Math.max(1, e.weight * 4) : 0.8;
        return (
          <g key={`${e.source}-${e.target}`}>
            <line
              x1={s.x} y1={s.y} x2={t.x} y2={t.y}
              stroke={isSel ? '#c85031' : '#94a3b8'}
              strokeWidth={isSel ? strokeW + 1.5 : strokeW}
              opacity={opacity}
              className={onClickEdge ? 'cursor-pointer hover:opacity-100' : ''}
              onClick={() => onClickEdge?.(e)}
            />
            {showLabels && e.kept && (
              <text
                x={(s.x + t.x) / 2}
                y={(s.y + t.y) / 2}
                fontSize={8}
                fill="#64748b"
                textAnchor="middle"
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
        return (
          <g key={v}>
            <circle
              cx={p.x} cy={p.y} r={isTarget ? 10 : isSelected ? 8 : 6}
              fill={isTarget ? '#c85031' : isSelected ? '#2563eb' : '#e2e8f0'}
              stroke={isTarget ? '#fff' : 'none'}
              strokeWidth={2}
              className={onClickNode ? 'cursor-pointer' : ''}
              onClick={() => onClickNode?.(i)}
            />
            <text
              x={p.x} y={p.y + 16}
              fontSize={9} fill={isTarget ? '#c85031' : '#475569'}
              textAnchor="middle"
              fontWeight={isTarget ? 600 : 400}
            >
              {v.length > 8 ? v.slice(0, 7) + '…' : v}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
