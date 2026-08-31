export interface FormalBundleLike {
  evidence: {
    primary_inference: { status: string };
    multiplicity: { supported: boolean | null };
  };
}

export function isFormalAvailable(bundle: FormalBundleLike | null): boolean {
  return Boolean(bundle && bundle.evidence.primary_inference.status === 'complete' && bundle.evidence.multiplicity.supported !== null);
}

export function formalAvailabilityLabel(local: FormalBundleLike | null, global: FormalBundleLike | null, equivalent = false): string {
  if (!local && !global) return 'Not audited';
  const available = Number(isFormalAvailable(local)) + Number(isFormalAvailable(global));
  if (equivalent) return available > 0 ? 'Formal inference available' : 'Formal inference unavailable';
  return available > 0 ? `Formal inference · ${available} / 2 displayed scopes available` : 'Formal inference unavailable';
}
