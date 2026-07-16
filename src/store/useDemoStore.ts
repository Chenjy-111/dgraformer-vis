import { create } from 'zustand';
import type {
  BaselineId,
  DatasetId,
  GraphLayout,
  GraphSource,
  Horizon,
  ExplanationDepth,
  SampleData,
  ScaleId,
  ViewMode,
} from '@/types/demo';
import type { Explanation, InteractionEvent } from '@/types/explanation';
import { DATASETS } from '@/data/datasets';
import { loadSample } from '@/data/loaders';

export interface SelectedEdge {
  source: number;
  target: number;
}

interface DemoState {
  // case selection
  dataset: DatasetId;
  sampleId: number;
  horizon: Horizon;
  target: number;

  // view
  view: ViewMode;

  // loaded artifact
  sample: SampleData | null;
  loading: boolean;

  // graph controls
  windowIdx: number;
  playing: boolean;
  graphSource: GraphSource;
  topkRatio: number; // 0..1
  edgeThreshold: number; // 0..1
  showFiltered: boolean;
  showEdgeLabels: boolean;
  highlightTarget: boolean;
  graphLayout: GraphLayout;
  graph3DSpacing: number;
  pruningDetail: boolean;
  inspectorCollapsed: boolean;

  // attention controls
  scale: ScaleId;
  head: number;
  showPatchBoundary: boolean;
  linkAttention: boolean;

  // explanation controls
  depth: ExplanationDepth;
  showFormulas: boolean;
  showAssumptions: boolean;
  showCaveats: boolean;
  showEvidence: boolean;

  // comparison
  compareBaseline: BaselineId;
  compareWindowA: number;
  compareWindowB: number;

  // selections (for explanation inspector)
  selectedEdge: SelectedEdge | null;
  selectedNode: number | null;
  hoveredPatch: { q: number; k: number } | null;
  selectedErrorStep: number | null;

  // explanation + history
  explanation: Explanation | null;
  pinned: Explanation[];
  history: InteractionEvent[];

  // guided tour
  tourActive: boolean;
  tourStep: number;

  // actions
  set: <K extends keyof DemoState>(key: K, value: DemoState[K]) => void;
  setCase: (patch: Partial<Pick<DemoState, 'dataset' | 'sampleId' | 'horizon' | 'target'>>) => void;
  setView: (v: ViewMode) => void;
  log: (action: string, oldVal?: string, newVal?: string) => void;
  setExplanation: (e: Explanation | null) => void;
  pin: (e: Explanation) => void;
  unpin: (id: string) => void;
  clearHistory: () => void;
  restore: (ev: InteractionEvent) => void;
  reset: () => void;
  loadCurrent: () => Promise<void>;
  startTour: () => void;
  stopTour: () => void;
  tourNext: () => void;
  tourPrev: () => void;
  gotoTourStep: (i: number) => void;
}

let evtSeq = 0;

export const useDemoStore = create<DemoState>((set, get) => ({
  dataset: 'ETTh1',
  sampleId: 0,
  horizon: 96,
  target: DATASETS.ETTh1.variables.length - 1,

  view: 'forecast',

  sample: null,
  loading: false,

  windowIdx: 0,
  playing: false,
  graphSource: 'dynamic',
  topkRatio: 0.4,
  edgeThreshold: 0.2,
  showFiltered: true,
  showEdgeLabels: false,
  highlightTarget: true,
  graphLayout: '3d-timeline',
  graph3DSpacing: 4.4,
  pruningDetail: false,
  inspectorCollapsed: false,

  scale: 1,
  head: 0,
  showPatchBoundary: true,
  linkAttention: true,

  depth: 'standard',
  showFormulas: true,
  showAssumptions: true,
  showCaveats: true,
  showEvidence: true,

  compareBaseline: 'MSGNet',
  compareWindowA: 0,
  compareWindowB: 1,

  selectedEdge: null,
  selectedNode: null,
  hoveredPatch: null,
  selectedErrorStep: null,

  explanation: null,
  pinned: [],
  history: [],

  tourActive: false,
  tourStep: 0,

  set: (key, value) => set({ [key]: value } as Partial<DemoState>),

  setCase: (patch) => {
    set({ ...patch, windowIdx: 0, selectedEdge: null, selectedNode: null });
    void get().loadCurrent();
  },

  setView: (v) => {
    const prev = get().view;
    set({ view: v });
    get().log('Switch view', prev, v);
  },

  log: (action, oldVal, newVal) => {
    const ev: InteractionEvent = {
      id: `evt-${++evtSeq}`,
      ts: Date.now(),
      action,
      oldValue: oldVal,
      newValue: newVal,
      view: get().view,
      explanationId: get().explanation?.id,
    };
    set((s) => ({ history: [ev, ...s.history].slice(0, 200) }));
  },

  setExplanation: (e) => set({ explanation: e }),

  pin: (e) => set((s) => (s.pinned.find((p) => p.id === e.id) ? s : { pinned: [...s.pinned, e] })),
  unpin: (id) => set((s) => ({ pinned: s.pinned.filter((p) => p.id !== id) })),

  clearHistory: () => set({ history: [] }),

  restore: (ev) => {
    // best-effort restore of view from a history event
    set({ view: ev.view });
    get().log('Restore from history', undefined, ev.action);
  },

  reset: () =>
    set({
      windowIdx: 0,
      playing: false,
      graphSource: 'dynamic',
      topkRatio: 0.4,
      edgeThreshold: 0.2,
      showFiltered: true,
      graphLayout: '3d-timeline',
      graph3DSpacing: 4.4,
      pruningDetail: false,
      scale: 1,
      head: 0,
      selectedEdge: null,
      selectedNode: null,
      hoveredPatch: null,
      selectedErrorStep: null,
    }),

  loadCurrent: async () => {
    const { dataset, sampleId, horizon, target, sample: currentSample } = get();
    set({ loading: true });
    const data = await loadSample(dataset, sampleId, horizon);
    const keepCurrentTarget = currentSample?.dataset === data.dataset && target >= 0 && target < data.variables.length;
    set({
      sample: data,
      target: keepCurrentTarget ? target : data.targetDefault,
      loading: false,
      windowIdx: Math.min(get().windowIdx, data.windows.length - 1),
    });
  },

  startTour: () => set({ tourActive: true, tourStep: 0 }),
  stopTour: () => set({ tourActive: false }),
  tourNext: () => set((s) => ({ tourStep: s.tourStep + 1 })),
  tourPrev: () => set((s) => ({ tourStep: Math.max(0, s.tourStep - 1) })),
  gotoTourStep: (i) => set({ tourStep: i }),
}));
