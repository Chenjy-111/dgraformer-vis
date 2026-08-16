import { create } from 'zustand';

export type WorkflowModel = 'DGraFormer' | 'MSGNet';
export type WorkflowStage = 'discover' | 'select' | 'test' | 'validate';

export interface WorkflowSelection {
  model: WorkflowModel;
  dataset: 'ETTh1';
  sample: number;
  contextType: 'window' | 'scale';
  contextIndex: number;
  source: number;
  target: number;
  sourceName: string;
  targetName: string;
}

interface WorkflowState {
  model: WorkflowModel;
  workspace: 1 | 2;
  stage: WorkflowStage;
  selection: WorkflowSelection | null;
  pendingIntervention: WorkflowSelection | null;
  evidenceStatus: 'idle' | 'loading' | 'available' | 'unavailable';
  setModel: (model: WorkflowModel) => void;
  selectRelation: (selection: WorkflowSelection) => void;
  testRelation: () => void;
  setEvidenceStatus: (status: WorkflowState['evidenceStatus']) => void;
  runGuidedExample: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  model: 'DGraFormer',
  workspace: 1,
  stage: 'discover',
  selection: null,
  pendingIntervention: null,
  evidenceStatus: 'idle',
  setModel: (model) => set({ model, workspace: 1, stage: 'discover', selection: null, pendingIntervention: null, evidenceStatus: 'idle' }),
  selectRelation: (selection) => set({ model: selection.model, selection, stage: 'select', evidenceStatus: 'idle' }),
  testRelation: () => {
    const selection = get().selection;
    if (!selection) return;
    set({ pendingIntervention: selection, workspace: 2, stage: 'test', evidenceStatus: 'loading' });
  },
  setEvidenceStatus: (evidenceStatus) => set({ evidenceStatus, stage: evidenceStatus === 'available' ? 'validate' : 'test' }),
  runGuidedExample: () => set({
    model: 'DGraFormer', workspace: 1, stage: 'select', evidenceStatus: 'idle', pendingIntervention: null,
    selection: { model: 'DGraFormer', dataset: 'ETTh1', sample: 0, contextType: 'window', contextIndex: 0, source: 0, target: 4, sourceName: 'HUFL', targetName: 'MUFL' },
  }),
}));
