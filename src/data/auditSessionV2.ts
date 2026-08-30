import type { AuditSession as V1Session, AuditSample, AuditTensor } from './auditSession';

export type V1AuditSession = V1Session;
export type EvidenceStatus = 'active' | 'inactive' | 'complete' | 'unavailable' | 'not_evaluated';
export type MissingReason = string;

export interface CaseEvidence {
  case_evidence_id: string;
  candidate_id: string;
  sample_id: number;
  context: Record<string, unknown>;
  scope: string;
  status: 'active' | 'inactive';
  focal_response: number | null;
  response_metric: 'prediction_delta_abs';
  controls: { protocol: 'all_unique_eligible'; unique_count: number; identities: string[]; responses?: number[]; mean: number | null; median: number | null };
  D: number | null;
  rank: number | null;
  percentile: number | null;
  baseline_reference: Record<string, unknown>;
  intervention_output_reference: Record<string, unknown> | null;
  response_metrics: Record<string, unknown>;
  graph_effect: Record<string, unknown>;
  formal_inference: { status: 'not_evaluated'; raw_p: null; BH_q: null; reason: string };
  provenance: Record<string, unknown>;
}

export interface CandidateRelation {
  candidate_id: string;
  source: number;
  target: number;
  source_name?: string;
  target_name?: string;
  scope: string;
  native_context_type: string;
  retained_contexts: unknown[];
  scale_index?: number;
  window_index?: number;
  family_id: string;
  case_evidence_ids: string[];
  cross_sample_evidence_id: string;
}

export interface PrimaryInference {
  status: 'complete' | 'unavailable';
  inference_unit: string;
  method: string | null;
  null: string | null;
  alternative: 'mean_D > 0';
  observed_statistic: number | null;
  raw_p: number | null;
  settings: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
  reason: MissingReason | null;
}

export interface SensitivityResult {
  name: string;
  role: 'sensitivity';
  method: string | null;
  statistic?: unknown;
  value?: unknown;
  CI?: unknown;
  p?: number | null;
  q?: number | null;
  settings: Record<string, unknown>;
  interpretation_boundary: string;
}

export interface CrossSampleEvidence {
  cross_sample_evidence_id: string;
  candidate_id: string;
  family_id: string;
  planned_samples: number[];
  active_samples: number[];
  inactive_samples: number[];
  coverage: number;
  D_values: Array<number | null>;
  D_case_references: string[];
  effect: Record<string, number | null>;
  primary_inference: PrimaryInference;
  multiplicity: { family_id: string; method: 'BH'; family_size: number; valid_raw_p_count: number; alpha: number; adjusted_q: number | null; supported: boolean | null; reason: string | null };
  sensitivity: SensitivityResult[];
  limitations: string[];
}

export interface HypothesisFamily {
  family_id: string;
  scope: string;
  selection_rule: string;
  context_identity_rule: string;
  members: string[];
  size: number;
  selection_frozen: true;
  multiple_testing: { method: 'BH'; alpha: number };
  family_membership_hash: string;
  raw_p_vector_hash: string;
  valid_raw_p_count: number;
}

export interface DependenceAudit {
  protocol_id: string;
  sample_ids: number[];
  raw_span: number | number[] | null;
  start_positions: number[] | null;
  minimum_start_gap: number | null;
  median_start_gap: number | null;
  adjacent_overlap_count: number | null;
  all_pair_overlap_count: number | null;
  same_continuous_series: boolean | null;
  classification: 'overlapping_time_windows' | 'non_overlapping_time_units' | 'unknown_dependence';
  derivation: string;
  inference_engine_selected: string | null;
  reason: MissingReason | null;
}

export interface AuditSessionV2 {
  schema_version: '2.0';
  session: Record<string, unknown> & { status: string };
  model: Record<string, unknown> & { adapter_id: string };
  dataset: Record<string, unknown>;
  checkpoint: Record<string, unknown>;
  audit_plan: Record<string, unknown>;
  samples: AuditSample[];
  relations: Array<Record<string, unknown>>;
  case_evidence: CaseEvidence[];
  candidate_relations: CandidateRelation[];
  hypothesis_families: HypothesisFamily[];
  cross_sample_evidence: CrossSampleEvidence[];
  dependence_audit: DependenceAudit[];
  validation: Record<string, unknown>;
  provenance: Record<string, unknown>;
  limitations: string[];
}

export type AuditSessionV2Validation = { ok: true; value: AuditSessionV2 } | { ok: false; errors: string[] };

const object = (value: unknown): value is Record<string, any> => typeof value === 'object' && value !== null && !Array.isArray(value);
const probability = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1;

function validateTensor(value: unknown, path: string, errors: string[]): void {
  if (!object(value) || !Array.isArray(value.shape) || !Array.isArray(value.values)) {
    errors.push(`${path} is not a tensor`);
    return;
  }
  if (!value.shape.every((item: unknown) => Number.isInteger(item) && (item as number) >= 0)) errors.push(`${path}.shape is invalid`);
  const dimensions: number[] = [];
  let cursor: unknown = value.values;
  while (Array.isArray(cursor)) {
    dimensions.push(cursor.length);
    cursor = cursor[0];
  }
  if (JSON.stringify(dimensions) !== JSON.stringify(value.shape)) errors.push(`${path}.shape does not match values`);
  const visit = (item: unknown): void => {
    if (Array.isArray(item)) item.forEach(visit);
    else if (typeof item !== 'number' || !Number.isFinite(item)) errors.push(`${path} contains a nonfinite/non-numeric value`);
  };
  visit(value.values);
}

function tensorShape(value: unknown): number[] | null {
  return object(value) && Array.isArray(value.shape) ? value.shape as number[] : null;
}

export function validateAuditSessionV2(input: unknown): AuditSessionV2Validation {
  const errors: string[] = [];
  if (!object(input) || input.schema_version !== '2.0') return { ok: false, errors: ['schema_version must be 2.0'] };
  const required = ['session', 'model', 'dataset', 'checkpoint', 'audit_plan', 'samples', 'relations', 'case_evidence', 'candidate_relations', 'hypothesis_families', 'cross_sample_evidence', 'dependence_audit', 'validation', 'provenance', 'limitations'];
  for (const key of required) if (!(key in input)) errors.push(`missing ${key}`);
  if (!Array.isArray(input.samples) || !Array.isArray(input.case_evidence) || !Array.isArray(input.candidate_relations) || !Array.isArray(input.hypothesis_families) || !Array.isArray(input.cross_sample_evidence) || !Array.isArray(input.dependence_audit)) return { ok: false, errors: [...errors, 'v2 collection fields must be arrays'] };
  const sampleIds = new Set<number>();
  input.samples.forEach((sample, index) => {
    if (!object(sample) || typeof sample.sample_index !== 'number') errors.push(`samples[${index}] is invalid`);
    else sampleIds.add(sample.sample_index);
    validateTensor(sample?.ground_truth, `samples[${index}].ground_truth`, errors);
    validateTensor(sample?.baseline_prediction, `samples[${index}].baseline_prediction`, errors);
    if (!Array.isArray(sample?.contexts) || sample.contexts.length === 0) errors.push(`samples[${index}] is missing graph contexts`);
    else sample.contexts.forEach((context: any, contextIndex: number) => {
      if (!object(context?.graphs) || Object.keys(context.graphs).length === 0) errors.push(`samples[${index}].contexts[${contextIndex}] is missing graph tensors`);
      else Object.entries(context.graphs).forEach(([name, tensor]) => validateTensor(tensor, `samples[${index}].contexts[${contextIndex}].graphs.${name}`, errors));
    });
  });
  const candidates = new Map(input.candidate_relations.map((candidate: any) => [candidate?.candidate_id, candidate]));
  const candidateIds = new Set(candidates.keys());
  const forbidden = ['case_raw_p', 'case_bh_q', 'case_significant', 'empirical_p', 'bh_adjusted_p'];
  input.case_evidence.forEach((item: any, index: number) => {
    if (!object(item) || !candidateIds.has(item.candidate_id) || !sampleIds.has(item.sample_id)) errors.push(`case_evidence[${index}] has invalid references`);
    const candidate = candidates.get(item?.candidate_id) as any;
    if (candidate && candidate.scope !== item?.scope) errors.push(`case_evidence[${index}] scope/candidate mismatch`);
    if (candidate && typeof candidate.window_index === 'number' && item?.context?.window_index !== candidate.window_index) errors.push(`case_evidence[${index}] trajectory/context mismatch`);
    if (candidate && typeof candidate.scale_index === 'number' && item?.context?.scale_index !== candidate.scale_index) errors.push(`case_evidence[${index}] trajectory/context mismatch`);
    for (const field of forbidden) if (field in (item ?? {})) errors.push(`case_evidence[${index}] contains forbidden ${field}`);
    for (const field of forbidden) if (field in (item?.response_metrics ?? {})) errors.push(`case_evidence[${index}].response_metrics contains forbidden ${field}`);
    if (!object(item?.controls) || item.controls.unique_count !== item.controls.identities?.length || new Set(item.controls.identities ?? []).size !== item.controls.identities?.length) errors.push(`case_evidence[${index}] controls are not unique/count-consistent`);
    if (item?.status === 'inactive' && (item.D !== null || item.focal_response !== null)) errors.push(`case_evidence[${index}] inactive D/focal must be null`);
    if (item?.status === 'active' && (!(typeof item.D === 'number') || Math.abs(item.D - (item.focal_response - item.controls.mean)) > 1e-9)) errors.push(`case_evidence[${index}] D mismatch`);
    if (item?.formal_inference?.status !== 'not_evaluated' || item?.formal_inference?.raw_p !== null || item?.formal_inference?.BH_q !== null) errors.push(`case_evidence[${index}] contains formal case inference`);
    const sample = input.samples.find((entry: any) => entry?.sample_index === item?.sample_id);
    const output = item?.intervention_output_reference?.value ?? item?.intervention_output_reference;
    if (item?.status === 'active' && object(output) && Array.isArray(output.values)) {
      validateTensor(output, `case_evidence[${index}].intervention_output_reference`, errors);
      const expected = tensorShape(sample?.baseline_prediction);
      if (expected && JSON.stringify(expected) !== JSON.stringify(tensorShape(output))) errors.push(`case_evidence[${index}] trajectory shape mismatch`);
    }
  });
  const membership = new Map<string, number>();
  input.hypothesis_families.forEach((family: any, index: number) => {
    if (family.size !== family.members?.length || new Set(family.members ?? []).size !== family.members?.length) errors.push(`hypothesis_families[${index}] size mismatch`);
    for (const id of family.members ?? []) membership.set(id, (membership.get(id) ?? 0) + 1);
  });
  for (const id of candidateIds) if (membership.get(id as string) !== 1) errors.push(`candidate ${String(id)} must belong to exactly one family`);
  input.cross_sample_evidence.forEach((item: any, index: number) => {
    for (const field of forbidden) if (field in (item ?? {})) errors.push(`cross_sample_evidence[${index}] contains forbidden ${field}`);
    if (!candidateIds.has(item.candidate_id)) errors.push(`cross_sample_evidence[${index}] candidate reference is invalid`);
    const candidate = candidates.get(item.candidate_id) as any;
    if (candidate && (candidate.family_id !== item.family_id || candidate.cross_sample_evidence_id !== item.cross_sample_evidence_id)) errors.push(`cross_sample_evidence[${index}] family/candidate reference mismatch`);
    if (item.primary_inference?.raw_p !== null && !probability(item.primary_inference?.raw_p)) errors.push(`cross_sample_evidence[${index}] raw_p is invalid`);
    if (item.multiplicity?.adjusted_q !== null && !probability(item.multiplicity?.adjusted_q)) errors.push(`cross_sample_evidence[${index}] adjusted_q is invalid`);
    if (typeof item.multiplicity?.adjusted_q === 'number' && item.multiplicity.supported !== (item.multiplicity.adjusted_q < item.multiplicity.alpha)) errors.push(`cross_sample_evidence[${index}] support/q mismatch`);
    if (item.primary_inference?.status === 'unavailable' && !item.primary_inference?.reason) errors.push(`cross_sample_evidence[${index}] unavailable inference needs a reason`);
    if (item.primary_inference?.status === 'unavailable' && (item.primary_inference?.raw_p !== null || item.multiplicity?.adjusted_q !== null || item.multiplicity?.supported !== null)) errors.push(`cross_sample_evidence[${index}] unavailable inference must not contain p/q/support`);
  });
  input.candidate_relations.forEach((candidate: any, index: number) => {
    const cross = input.cross_sample_evidence.find((item: any) => item?.cross_sample_evidence_id === candidate?.cross_sample_evidence_id);
    if (!cross) errors.push(`candidate_relations[${index}] cross-sample reference is invalid`);
    const family = input.hypothesis_families.find((item: any) => item?.family_id === candidate?.family_id);
    if (!family?.members?.includes(candidate?.candidate_id)) errors.push(`candidate_relations[${index}] family reference is invalid`);
  });
  input.dependence_audit.forEach((item: any, index: number) => { if (item?.classification === 'unknown_dependence' && !item.reason) errors.push(`dependence_audit[${index}] unknown dependence needs a reason`); });
  return errors.length ? { ok: false, errors } : { ok: true, value: input as unknown as AuditSessionV2 };
}

export function parseAuditSessionV2(text: string): AuditSessionV2Validation {
  try { return validateAuditSessionV2(JSON.parse(text)); }
  catch (error) { return { ok: false, errors: [`Invalid JSON: ${error instanceof Error ? error.message : String(error)}`] }; }
}

export type { AuditTensor };
