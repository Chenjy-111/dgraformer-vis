import { validateAuditSessionV2, type AuditSessionV2, type CandidateRelation, type CaseEvidence, type CrossSampleEvidence, type DependenceAudit, type HypothesisFamily } from './auditSessionV2';

const BUILT_IN: Record<string, string> = {
  DGraFormer: './data/evidence/dgraformer_etth1_session_v2.json',
  MSGNet: './data/evidence/msgnet_etth1_session_v2.json',
};
const cache = new Map<string, Promise<AuditSessionV2>>();

export function loadBuiltInSessionV2(model: string): Promise<AuditSessionV2> {
  const url = BUILT_IN[model];
  if (!url) return Promise.reject(new Error(`No built-in Session v2 is registered for ${model}.`));
  if (!cache.has(model)) cache.set(model, fetch(url).then(async response => {
    if (!response.ok) throw new Error(`Session v2 request failed (${response.status}).`);
    const result = validateAuditSessionV2(await response.json());
    if (!result.ok) throw new Error(`Built-in Session v2 failed validation: ${result.errors.slice(0, 4).join('; ')}`);
    return result.value;
  }));
  return cache.get(model)!;
}

export interface CandidateBundle {
  candidate: CandidateRelation;
  evidence: CrossSampleEvidence;
  family: HypothesisFamily;
  dependence: DependenceAudit | null;
}

export function exactCandidate(session: AuditSessionV2, predicate: (candidate: CandidateRelation) => boolean): CandidateBundle | null {
  const candidate = session.candidate_relations.find(predicate);
  if (!candidate) return null;
  const evidence = session.cross_sample_evidence.find(item => item.cross_sample_evidence_id === candidate.cross_sample_evidence_id && item.candidate_id === candidate.candidate_id && item.family_id === candidate.family_id);
  const family = session.hypothesis_families.find(item => item.family_id === candidate.family_id && item.members.includes(candidate.candidate_id));
  if (!evidence || !family) return null;
  const dependence = session.dependence_audit.find(item => item.protocol_id === (session.audit_plan as any)?.sample_protocol?.protocol_id) ?? session.dependence_audit[0] ?? null;
  return { candidate, evidence, family, dependence };
}

export function exactCase(session: AuditSessionV2, candidate: CandidateRelation, sampleId: number): CaseEvidence | null {
  const expectedId = candidate.case_evidence_ids.find(id => session.case_evidence.some(item => item.case_evidence_id === id && item.candidate_id === candidate.candidate_id && item.sample_id === sampleId));
  return expectedId ? session.case_evidence.find(item => item.case_evidence_id === expectedId) ?? null : null;
}

export function sampleById(session: AuditSessionV2, sampleId: number) {
  return session.samples.find(sample => sample.sample_index === sampleId) ?? null;
}

export function relationGroups(session: AuditSessionV2) {
  const groups = new Map<string, { source: number; target: number; sourceName: string; targetName: string; candidates: CandidateRelation[]; retained: number[] }>();
  for (const candidate of session.candidate_relations) {
    const key = `${candidate.source}->${candidate.target}`;
    const current = groups.get(key) ?? { source: candidate.source, target: candidate.target, sourceName: candidate.source_name ?? String(candidate.source), targetName: candidate.target_name ?? String(candidate.target), candidates: [], retained: [] };
    current.candidates.push(candidate);
    current.retained = [...new Set([...current.retained, ...candidate.retained_contexts.filter((value): value is number => typeof value === 'number')])].sort((a, b) => a - b);
    groups.set(key, current);
  }
  return [...groups.values()];
}
