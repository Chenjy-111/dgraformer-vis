import type { ExplanationDepth, ViewMode } from './demo';

export type { ExplanationDepth };

export interface EvidenceItem {
  label: string;
  value: string;
  tone?: 'neutral' | 'kept' | 'filtered' | 'warn';
}

export interface ExplanationQuality {
  evidence: number; // 0..1
  specificity: number;
  mechanism: number;
  uncertainty: number;
}

export interface Explanation {
  id: string;
  title: string;
  mode: ViewMode;
  selectionLabel: string;
  summary: string;
  evidence: EvidenceItem[];
  formula?: string; // pre-rendered KaTeX HTML at build time
  assumption?: string;
  caveat?: string;
  whatChanged?: string;
  nextStep?: string;
  quality: ExplanationQuality;
}

export interface InteractionEvent {
  id: string;
  ts: number;
  action: string;
  oldValue?: string;
  newValue?: string;
  view: ViewMode;
  explanationId?: string;
}
