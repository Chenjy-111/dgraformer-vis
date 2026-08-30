import { create } from 'zustand';
import { parseCurrentAuditSession, type AuditSessionV2 } from '@/data/auditSessionV2';
import type { WorkflowModel } from './useWorkflowStore';

type ImportState = 'idle' | 'reading' | 'validating' | 'ready' | 'invalid';

interface AuditSessionState {
  source: 'built_in' | 'imported';
  sessionV2: AuditSessionV2 | null;
  fileName: string | null;
  previousModel: WorkflowModel | null;
  importState: ImportState;
  errors: string[];
  importFile: (file: File, previousModel: WorkflowModel) => Promise<AuditSessionV2 | null>;
  importText: (text: string, fileName: string, previousModel: WorkflowModel) => AuditSessionV2 | null;
  clearError: () => void;
  closeSession: () => void;
}

function validateImportedText(text: string) {
  const result = parseCurrentAuditSession(text);
  return result.ok
    ? { value: result.value, errors: [] as string[] }
    : { value: null, errors: result.errors };
}

export const useAuditSessionStore = create<AuditSessionState>((set, get) => ({
  source: 'built_in',
  sessionV2: null,
  fileName: null,
  previousModel: null,
  importState: 'idle',
  errors: [],
  importFile: async (file, previousModel) => {
    set({ importState: 'reading', errors: [] });
    let text: string;
    try {
      text = await file.text();
    } catch (error) {
      set({
        importState: 'invalid',
        errors: ['The selected file could not be read: ' + (error instanceof Error ? error.message : String(error))],
      });
      return null;
    }
    set({ importState: 'validating' });
    return get().importText(text, file.name, previousModel);
  },
  importText: (text, fileName, previousModel) => {
    const result = validateImportedText(text);
    if (!result.value) {
      set({ importState: 'invalid', errors: result.errors });
      return null;
    }
    set({
      source: 'imported',
      sessionV2: result.value,
      fileName,
      previousModel: get().source === 'imported' ? get().previousModel : previousModel,
      importState: 'ready',
      errors: [],
    });
    return result.value;
  },
  clearError: () => set({ errors: [], importState: get().sessionV2 ? 'ready' : 'idle' }),
  closeSession: () => set({
    source: 'built_in',
    sessionV2: null,
    fileName: null,
    previousModel: null,
    importState: 'idle',
    errors: [],
  }),
}));
