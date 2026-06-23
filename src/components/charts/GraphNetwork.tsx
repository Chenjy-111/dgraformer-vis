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
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  }

  const focused = highlightTarget ? target : null;
  const hasFocus = focused !== null;

  const targetColor = '#c85031';
  const selectColor = '#2563eb';
  const normalColor = '#94a3b8';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Edges */}
      {(showFiltered ? edges : filtered).map((e) => {
        if (e.weight < threshold) return null;
        const s = nodePos(e.source);
        const t = nodePos(e.target);
        const isSel =
          selectedEdge?.source === e.source && selectedEdge?.target === e.target;
        const isTargetEdge =
          hasFocus && (e.source === focused || e.target === focused);

        let stroke: string;
        let opacity: number;
        let strokeW: number;

        if (isSel) {
          stroke = selectColor;
          opacity = 1;
          strokeW = Math.max(1.5, e.weight * 3.5);
        } else if (isTargetEdge && e.kept) {
          stroke = targetColor;
          opacity = 0.8;
          strokeW = Math.max(1, e.weight * 2.8);
        } else if (e.kept) {
          stroke = normalColor;
          opacity = hasFocus ? 0.25 : 0.45;
          strokeW = Math.max(0.8, e.weight * 2.5);
        } else {
          stroke = normalColor;
          opacity = 0.12;
          strokeW = 0.6;
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
            {showLabels && e.kept && (
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