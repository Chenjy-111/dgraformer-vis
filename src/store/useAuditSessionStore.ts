import { create } from 'zustand';
import { parseAuditSession, type AuditSession } from '@/data/auditSession';
import type { WorkflowModel } from './useWorkflowStore';

type ImportState = 'idle' | 'reading' | 'validating' | 'ready' | 'invalid';

interface AuditSessionState {
  source: 'built_in' | 'imported';
  session: AuditSession | null;
  fileName: string | null;
  previousModel: WorkflowModel | null;
  importState: ImportState;
  errors: string[];
  importFile: (file: File, previousModel: WorkflowModel) => Promise<AuditSession | null>;
  importText: (text: string, fileName: string, previousModel: WorkflowModel) => AuditSession | null;
  clearError: () => void;
  closeSession: () => void;
}

function validatedState(text: string, fileName: string, previousModel: WorkflowModel) {
  const result = parseAuditSession(text);
  if (!result.valid) return { session: null, errors: result.errors };
  return { session: result.session, errors: [] as string[] };
}

export const useAuditSessionStore = create<AuditSessionState>((set, get) => ({
  source: 'built_in',
  session: null,
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
        errors: [`The selected file could not be read: ${error instanceof Error ? error.message : String(error)}`],
      });
      return null;
    }
    set({ importState: 'validating' });
    return get().importText(text, file.name, previousModel);
  },
  importText: (text, fileName, previousModel) => {
    const result = validatedState(text, fileName, previousModel);
    if (!result.session) {
      // Atomic failure: keep the current built-in/imported data source untouched.
      set({ importState: 'invalid', errors: result.errors });
      return null;
    }
    set({
      source: 'imported',
      session: result.session,
      fileName,
      previousModel: get().source === 'imported' ? get().previousModel : previousModel,
      importState: 'ready',
      errors: [],
    });
    return result.session;
  },
  clearError: () => set({ errors: [], importState: get().session ? 'ready' : 'idle' }),
  closeSession: () => set({
    source: 'built_in',
    session: null,
    fileName: null,
    previousModel: null,
    importState: 'idle',
    errors: [],
  }),
}));
