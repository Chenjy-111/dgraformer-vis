import type { GraphEdge, SampleData, WindowData } from '@/types/demo';

export function activeMatrix(win: WindowData, source: 'static' | 'dynamic' | 'sparse' | 'difference'): number[][] {
  if (source === 'static') return win.static_graph;
  if (source === 'sparse') return win.sparse_graph;
  if (source === 'difference') {
    const N = win.dynamic_graph.length;
    return Array.from({ length: N }, (_, i) =>
      Array.from({ length: N }, (_, j) => Math.round((win.dynamic_graph[i][j] - win.static_graph[i][j]) * 1000) / 1000)
    );
  }
  return win.dynamic_graph;
}

/** Recompute kept/filtered split for a custom keep ratio (UI slider). */
export function recomputeTopK(edges: GraphEdge[], keepRatio: number): GraphEdge[] {
  const k = Math.max(1, Math.round(edges.length * keepRatio));
  return edges.map((e) => ({ ...e, kept: e.rank <= k }));
}

export function edgesForThreshold(edges: GraphEdge[], threshold: number): GraphEdge[] {
  return edges.filter((e) => e.weight >= threshold);
}

export function nodeDegree(edges: GraphEdge[], node: number): { out: number; in: number; strength: number } {
  let out = 0;
  let inc = 0;
  let strength = 0;
  for (const e of edges) {
    if (!e.kept) continue;
    if (e.source === node) {
      out++;
      strength += e.weight;
    }
    if (e.target === node) inc++;
  }
  return { out, in: inc, strength: Math.round(strength * 1000) / 1000 };
}

export function edgeStabilityAcrossWindows(sample: SampleData, source: number, target: number): number {
  // fraction of windows where this edge is kept
  let kept = 0;
  for (const w of sample.windows) {
    if (w.kept_edges.some((e) => e.source === source && e.target === target)) kept++;
  }
  return Math.round((kept / sample.windows.length) * 100) / 100;
}

export function classifyNodeRole(edges: GraphEdge[], node: number, N: number): string {
  const deg = nodeDegree(edges, node);
  if (deg.out === 0 && deg.in === 0) return 'isolated (no retained correlations in this window)';
  if (deg.out >= Math.max(2, N / 3)) return 'hub (propagates information to many variables)';
  if (deg.in >= Math.max(2, N / 3)) return 'sink (aggregates information from many variables)';
  return 'peripheral (a few retained correlations)';
}
