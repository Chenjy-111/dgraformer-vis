import { create } from 'zustand';
import { parseAuditSession, type AuditSession } from '@/data/auditSession';
import { parseAuditSessionV2, type AuditSessionV2 } from '@/data/auditSessionV2';
import type { WorkflowModel } from './useWorkflowStore';

type ImportState = 'idle' | 'reading' | 'validating' | 'ready' | 'invalid';

interface AuditSessionState {
  source: 'built_in' | 'imported';
  session: AuditSession | null;
  sessionV2: AuditSessionV2 | null;
  fileName: string | null;
  previousModel: WorkflowModel | null;
  importState: ImportState;
  errors: string[];
  importFile: (file: File, previousModel: WorkflowModel) => Promise<AuditSession | AuditSessionV2 | null>;
  importText: (text: string, fileName: string, previousModel: WorkflowModel) => AuditSession | AuditSessionV2 | null;
  clearError: () => void;
  closeSession: () => void;
}

function validatedState(text: string, fileName: string, previousModel: WorkflowModel) {
  try {
    const header = JSON.parse(text) as { schema_version?: unknown };
    if (header?.schema_version === '2.0') {
      const result = parseAuditSessionV2(text);
      if (!result.ok) return { session: null, sessionV2: null, errors: result.errors };
      return { session: null, sessionV2: result.value, errors: [] as string[] };
    }
  } catch {
    // The version-specific parser below returns the canonical JSON error.
  }
  const result = parseAuditSession(text);
  if (!result.valid) return { session: null, sessionV2: null, errors: result.errors };
  return { session: result.session, sessionV2: null, errors: [] as string[] };
}

export const useAuditSessionStore = create<AuditSessionState>((set, get) => ({
  source: 'built_in',
  session: null,
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
        errors: [`The selected file could not be read: ${error instanceof Error ? error.message : String(error)}`],
      });
      return null;
    }
    set({ importState: 'validating' });
    return get().importText(text, file.name, previousModel);
  },
  importText: (text, fileName, previousModel) => {
    const result = validatedState(text, fileName, previousModel);
    if (!result.session && !result.sessionV2) {
      // Atomic failure: keep the current built-in/imported data source untouched.
      set({ importState: 'invalid', errors: result.errors });
      return null;
    }
    set({
      source: 'imported',
      session: result.session,
      sessionV2: result.sessionV2,
      fileName,
      previousModel: get().source === 'imported' ? get().previousModel : previousModel,
      importState: 'ready',
      errors: [],
    });
    return result.session ?? result.sessionV2;
  },
  clearError: () => set({ errors: [], importState: get().session || get().sessionV2 ? 'ready' : 'idle' }),
  closeSession: () => set({
    source: 'built_in',
    session: null,
    sessionV2: null,
    fileName: null,
    previousModel: null,
    importState: 'idle',
    errors: [],
  }),
}));
