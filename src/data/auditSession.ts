export const AUDIT_SESSION_VERSION = 'dgrainsight.audit_session.v1' as const;

export type AuditModelName = string;
export type NativeContextType = string;
export type EvidenceScope = 'local' | 'broader_context';
export type EvidenceStatus = 'available' | 'not_exposed' | 'missing' | 'unavailable';

export interface AuditTensor {
  dtype: string;
  shape: number[];
  axis_order: string[];
  values: unknown[];
  sha256?: string;
}

export interface NullableTensor {
  status: 'available' | 'missing' | 'unavailable';
  value: AuditTensor | null;
  reason: string | null;
}

export interface GraphContext {
  context_id: string;
  type: NativeContextType;
  index: number;
  layer?: number;
  node_count: number;
  graphs: Record<string, AuditTensor>;
  native_metadata: Record<string, unknown>;
}

export interface AuditSample {
  sample_id: string;
  display_id: number | null;
  split: 'test';
  sample_index: number;
  history: NullableTensor;
  ground_truth: AuditTensor;
  baseline_prediction: AuditTensor;
  sample_metrics: Record<string, number | number[] | null>;
  contexts: GraphContext[];
  provenance: Record<string, unknown>;
  model_specific?: Record<string, unknown>;
}

export interface AuditRelationOccurrence {
  context_id: string;
  weight: number;
  retained: boolean;
  rank?: number | null;
}

export interface AuditRelation {
  relation_id: string;
  sample_id: string;
  source: number;
  target: number;
  source_name: string;
  target_name: string;
  native_occurrences: AuditRelationOccurrence[];
  evidence_ids: string[];
  model_specific?: Record<string, unknown>;
}

export interface ExactSelection {
  model: AuditModelName;
  dataset: string;
  sample_id: string;
  sample_index: number;
  context_type: string;
  context_id: string;
  context_index: number | 'all_applicable';
  layer?: number | null;
  source: number;
  target: number;
  source_name: string;
  target_name: string;
  scope: EvidenceScope;
}

export interface ControlEvidence {
  status: 'available' | 'missing' | 'not_applicable';
  protocol: string | null;
  count: number | null;
  random_seed: number | null;
  values: {
    status: 'available' | 'missing' | 'not_applicable';
    value: number[] | null;
    reason: string | null;
  };
  records: Record<string, unknown>[];
  summary: Record<string, number | number[] | null>;
  records_sha256?: string | null;
  model_specific?: Record<string, unknown>;
}

export interface EvidencePayload {
  baseline_output_ref: string;
  intervention_output: NullableTensor;
  metrics: Record<string, number | number[] | null>;
  statistics: Record<string, number | number[] | null>;
  metric_status: Record<string, { status: string; reason: string | null }>;
  controls: ControlEvidence;
  graph_effect: Record<string, unknown>;
  diagnostic_localization: Record<string, unknown> | null;
  limitations: string[];
  provenance: Record<string, unknown>;
  model_specific?: Record<string, unknown>;
}

export interface AuditEvidenceRecord {
  evidence_id: string;
  relation_id: string;
  selection: ExactSelection;
  status: EvidenceStatus;
  reason: string | null;
  value: EvidencePayload | null;
}

export interface AuditSession {
  schema_version: typeof AUDIT_SESSION_VERSION;
  session: {
    session_id: string;
    created_at: string;
    generator: { name: string; version: string; run_id: string };
    source_mode: 'offline_audit';
    title?: string | null;
  };
  model: {
    name: AuditModelName;
    adapter: string;
    adapter_id: string;
    native_context_type: NativeContextType;
    source_repository?: string | null;
    source_commit?: string | null;
    configuration: Record<string, unknown>;
  };
  dataset: {
    name: string;
    format: string;
    sha256: string;
    variables: string[];
    date_column: string;
    features: string;
    target: string;
    frequency: string;
    seq_len: number;
    label_len: number;
    pred_len: number;
    original_path?: string | null;
  };
  checkpoint: { sha256: string; format: string; load_status: 'validated'; original_path?: string | null };
  audit_plan: {
    split: 'test';
    sample_indices: number[];
    relation_count: number;
    local_scope: 'exact_native_context';
    broader_context_scope: 'not_requested' | 'all_applicable_native_contexts';
    candidate_protocol?: string | null;
    control_protocol?: string | null;
    multiple_comparison_protocol?: string | null;
  };
  samples: AuditSample[];
  relations: AuditRelation[];
  evidence_records: AuditEvidenceRecord[];
  evidence_summary: {
    local_case_count: number;
    broader_context_case_count: number;
    local_bh_supported_count: number | null;
    broader_context_bh_supported_count: number | null;
    negative_evidence_preserved: true;
    not_exposed_case_count?: number;
    missing_case_count?: number;
  };
  cross_run_evidence: { status: string; value: Record<string, unknown> | null; reason: string | null };
  provenance: {
    session_generation_run_id: string;
    validation: { kind: string; status: 'passed'; report_sha256: string };
    config_sha256: string;
    source_runs: Array<Record<string, unknown>>;
    commands: string[];
    environment: Record<string, unknown>;
    code_references: string[];
    source_artifacts: Array<Record<string, unknown>>;
  };
  limitations: string[];
  model_specific?: Record<string, unknown>;
}

export type AuditSessionValidationResult =
  | { valid: true; session: AuditSession; errors: [] }
  | { valid: false; session: null; errors: string[] };

const TOP_LEVEL_REQUIRED = [
  'schema_version', 'session', 'model', 'dataset', 'checkpoint', 'audit_plan', 'samples',
  'relations', 'evidence_records', 'evidence_summary', 'cross_run_evidence', 'provenance', 'limitations',
] as const;
const TOP_LEVEL_ALLOWED = new Set<string>([...TOP_LEVEL_REQUIRED, 'model_specific']);
const SHA256 = /^[a-f0-9]{64}$/;
const MAX_ERRORS = 40;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value);
}

function add(errors: string[], message: string) {
  if (errors.length < MAX_ERRORS) errors.push(message);
}

function requireRecord(value: unknown, path: string, errors: string[]): Record<string, unknown> | null {
  if (!isRecord(value)) {
    add(errors, `${path} must be an object.`);
    return null;
  }
  return value;
}

function requireFields(value: Record<string, unknown>, fields: readonly string[], path: string, errors: string[]) {
  for (const field of fields) if (!(field in value)) add(errors, `${path}.${field} is required.`);
}

function validateSha(value: unknown, path: string, errors: string[]) {
  if (typeof value !== 'string' || !SHA256.test(value)) add(errors, `${path} must be a lowercase SHA-256 hash.`);
}

function inferNumericShape(value: unknown, path: string, errors: string[]): number[] | null {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) add(errors, `${path} contains a non-finite number.`);
    return [];
  }
  if (typeof value === 'boolean') return [];
  if (!Array.isArray(value)) {
    add(errors, `${path} must contain only finite numbers, booleans, or nested arrays.`);
    return null;
  }
  if (value.length === 0) return [0];
  const first = inferNumericShape(value[0], `${path}[0]`, errors);
  if (!first) return null;
  for (let index = 1; index < value.length; index += 1) {
    const next = inferNumericShape(value[index], `${path}[${index}]`, errors);
    if (!next || next.length !== first.length || next.some((size, axis) => size !== first[axis])) {
      add(errors, `${path} is ragged.`);
      return null;
    }
  }
  return [value.length, ...first];
}

function validateTensor(value: unknown, path: string, errors: string[]): value is AuditTensor {
  const tensor = requireRecord(value, path, errors);
  if (!tensor) return false;
  requireFields(tensor, ['dtype', 'shape', 'axis_order', 'values'], path, errors);
  if (typeof tensor.dtype !== 'string' || tensor.dtype.length === 0) add(errors, `${path}.dtype must be a string.`);
  if (!Array.isArray(tensor.shape) || tensor.shape.length === 0 || tensor.shape.some(size => !isInteger(size) || size < 0)) {
    add(errors, `${path}.shape must contain non-negative integers.`);
  }
  if (!Array.isArray(tensor.axis_order) || tensor.axis_order.some(axis => typeof axis !== 'string' || !axis)) {
    add(errors, `${path}.axis_order must contain labels.`);
  }
  if (Array.isArray(tensor.shape) && Array.isArray(tensor.axis_order) && tensor.shape.length !== tensor.axis_order.length) {
    add(errors, `${path} axis count does not match tensor rank.`);
  }
  const actual = inferNumericShape(tensor.values, `${path}.values`, errors);
  const declaredShape = Array.isArray(tensor.shape) ? tensor.shape : null;
  if (actual && declaredShape && (
    actual.length !== declaredShape.length || actual.some((size, index) => size !== declaredShape[index])
  )) add(errors, `${path} declared shape does not match stored values.`);
  if (tensor.sha256 !== undefined) validateSha(tensor.sha256, `${path}.sha256`, errors);
  return true;
}

function validateNullableTensor(value: unknown, path: string, errors: string[]): value is NullableTensor {
  const wrapper = requireRecord(value, path, errors);
  if (!wrapper) return false;
  requireFields(wrapper, ['status', 'value', 'reason'], path, errors);
  if (wrapper.status === 'available') {
    if (wrapper.reason !== null) add(errors, `${path}.reason must be null when available.`);
    validateTensor(wrapper.value, `${path}.value`, errors);
  } else if (wrapper.status === 'missing' || wrapper.status === 'unavailable') {
    if (wrapper.value !== null || typeof wrapper.reason !== 'string' || !wrapper.reason) {
      add(errors, `${path} missing/unavailable state requires value=null and a reason.`);
    }
  } else add(errors, `${path}.status is unsupported.`);
  return true;
}

function validateMetricMap(value: unknown, path: string, errors: string[]) {
  const metrics = requireRecord(value, path, errors);
  if (!metrics) return;
  for (const [name, metric] of Object.entries(metrics)) {
    if (metric === null || (typeof metric === 'number' && Number.isFinite(metric))) continue;
    if (Array.isArray(metric) && metric.every(item => typeof item === 'number' && Number.isFinite(item))) continue;
    add(errors, `${path}.${name} must be a finite number, numeric array, or null.`);
  }
}

function validateControls(value: unknown, path: string, errors: string[]) {
  const controls = requireRecord(value, path, errors);
  if (!controls) return;
  requireFields(controls, ['status', 'protocol', 'count', 'random_seed', 'values', 'records', 'summary'], path, errors);
  const values = requireRecord(controls.values, `${path}.values`, errors);
  if (controls.status === 'available') {
    if (!values || values.status !== 'available' || !Array.isArray(values.value) ||
      values.value.some(item => typeof item !== 'number' || !Number.isFinite(item))) {
      add(errors, `${path} available controls require stored finite values.`);
    } else if (controls.count !== values.value.length) add(errors, `${path}.count does not match stored controls.`);
  } else if (controls.status === 'missing' || controls.status === 'not_applicable') {
    if (!values || values.value !== null || typeof values.reason !== 'string' || !values.reason) {
      add(errors, `${path} missing/not-applicable controls require value=null and a reason.`);
    }
  } else add(errors, `${path}.status is unsupported.`);
  if (!Array.isArray(controls.records) || controls.records.some(item => !isRecord(item))) {
    add(errors, `${path}.records must be an array of objects.`);
  }
  validateMetricMap(controls.summary, `${path}.summary`, errors);
  if (controls.records_sha256 !== undefined && controls.records_sha256 !== null) {
    validateSha(controls.records_sha256, `${path}.records_sha256`, errors);
  }
}

export function validateAuditSession(input: unknown): AuditSessionValidationResult {
  const errors: string[] = [];
  const root = requireRecord(input, 'session', errors);
  if (!root) return { valid: false, session: null, errors };
  requireFields(root, TOP_LEVEL_REQUIRED, 'session', errors);
  for (const key of Object.keys(root)) if (!TOP_LEVEL_ALLOWED.has(key)) add(errors, `session.${key} is not allowed in v1.`);
  if (root.schema_version !== AUDIT_SESSION_VERSION) {
    add(errors, `session.schema_version must be ${AUDIT_SESSION_VERSION}.`);
  }

  const metadata = requireRecord(root.session, 'session.session', errors);
  if (metadata) {
    requireFields(metadata, ['session_id', 'created_at', 'generator', 'source_mode'], 'session.session', errors);
    if (typeof metadata.session_id !== 'string' || !metadata.session_id) add(errors, 'session.session.session_id is required.');
    if (typeof metadata.created_at !== 'string' || Number.isNaN(Date.parse(metadata.created_at))) {
      add(errors, 'session.session.created_at must be a date-time string.');
    }
    if (metadata.source_mode !== 'offline_audit') add(errors, 'session.session.source_mode must be offline_audit.');
    const generator = requireRecord(metadata.generator, 'session.session.generator', errors);
    if (generator) {
      requireFields(generator, ['name', 'version', 'run_id'], 'session.session.generator', errors);
      if (generator.name !== 'DGraInsight offline audit pipeline') add(errors, 'session generator is incompatible.');
    }
  }

  const model = requireRecord(root.model, 'session.model', errors);
  const modelName = model?.name;
  const adapterId = model?.adapter_id;
  const nativeType = model?.native_context_type;
  if (model) {
    requireFields(model, ['name', 'adapter', 'adapter_id', 'native_context_type', 'configuration'], 'session.model', errors);
    const expected = adapterId === 'dgraformer'
      ? ['DGraFormer', 'DGraFormerAdapter', 'window']
      : adapterId === 'msgnet' ? ['MSGNet', 'MSGNetAdapter', 'scale']
        : adapterId === 'mtgnn' ? ['MTGNN', 'MTGNNAdapter', 'global_graph'] : null;
    if (expected && (model.name !== expected[0] || model.adapter !== expected[1] || nativeType !== expected[2])) {
      add(errors, 'session.model does not preserve a supported model-native adapter mapping.');
    }
    if (typeof model.name !== 'string' || !model.name || typeof model.adapter !== 'string' || !model.adapter ||
      typeof adapterId !== 'string' || !/^[a-z][a-z0-9_-]*$/.test(adapterId) ||
      typeof nativeType !== 'string' || !nativeType) {
      add(errors, 'session.model must declare a non-empty self-describing adapter contract.');
    }
    if (!isRecord(model.configuration)) add(errors, 'session.model.configuration must be an object.');
  }

  const dataset = requireRecord(root.dataset, 'session.dataset', errors);
  const variables = Array.isArray(dataset?.variables) ? dataset.variables : [];
  if (dataset) {
    requireFields(dataset, [
      'name', 'format', 'sha256', 'variables', 'date_column', 'features', 'target', 'frequency',
      'seq_len', 'label_len', 'pred_len',
    ], 'session.dataset', errors);
    validateSha(dataset.sha256, 'session.dataset.sha256', errors);
    if (!variables.length || variables.some(item => typeof item !== 'string' || !item) || new Set(variables).size !== variables.length) {
      add(errors, 'session.dataset.variables must be a non-empty unique string array.');
    }
    for (const field of ['seq_len', 'label_len', 'pred_len']) {
      if (!isInteger(dataset[field]) || (dataset[field] as number) < 1) add(errors, `session.dataset.${field} must be positive.`);
    }
  }
  const checkpoint = requireRecord(root.checkpoint, 'session.checkpoint', errors);
  if (checkpoint) {
    requireFields(checkpoint, ['sha256', 'format', 'load_status'], 'session.checkpoint', errors);
    validateSha(checkpoint.sha256, 'session.checkpoint.sha256', errors);
    if (checkpoint.load_status !== 'validated') add(errors, 'session.checkpoint.load_status must be validated.');
  }

  const samples = Array.isArray(root.samples) ? root.samples : [];
  if (!Array.isArray(root.samples) || samples.length === 0) add(errors, 'session.samples must be a non-empty array.');
  const sampleById = new Map<string, Record<string, unknown>>();
  const contextsBySample = new Map<string, Map<string, Record<string, unknown>>>();
  const sampleOrder: number[] = [];
  samples.forEach((value, samplePosition) => {
    const path = `session.samples[${samplePosition}]`;
    const sample = requireRecord(value, path, errors);
    if (!sample) return;
    requireFields(sample, [
      'sample_id', 'display_id', 'split', 'sample_index', 'history', 'ground_truth',
      'baseline_prediction', 'sample_metrics', 'contexts', 'provenance',
    ], path, errors);
    if (typeof sample.sample_id !== 'string' || !sample.sample_id || sampleById.has(sample.sample_id)) {
      add(errors, `${path}.sample_id must be unique.`);
      return;
    }
    if (!isInteger(sample.sample_index) || sample.sample_index < 0 || sample.sample_id !== `test:${sample.sample_index}`) {
      add(errors, `${path} has an invalid canonical sample identity.`);
    }
    sampleById.set(sample.sample_id, sample);
    sampleOrder.push(sample.sample_index as number);
    validateNullableTensor(sample.history, `${path}.history`, errors);
    validateTensor(sample.ground_truth, `${path}.ground_truth`, errors);
    validateTensor(sample.baseline_prediction, `${path}.baseline_prediction`, errors);
    validateMetricMap(sample.sample_metrics, `${path}.sample_metrics`, errors);
    const contextMap = new Map<string, Record<string, unknown>>();
    if (!Array.isArray(sample.contexts) || sample.contexts.length === 0) add(errors, `${path}.contexts must be non-empty.`);
    else sample.contexts.forEach((contextValue, contextPosition) => {
      const contextPath = `${path}.contexts[${contextPosition}]`;
      const context = requireRecord(contextValue, contextPath, errors);
      if (!context) return;
      requireFields(context, ['context_id', 'type', 'index', 'node_count', 'graphs', 'native_metadata'], contextPath, errors);
      if (typeof context.context_id !== 'string' || !context.context_id || contextMap.has(context.context_id)) {
        add(errors, `${contextPath}.context_id must be unique within its sample.`);
        return;
      }
      contextMap.set(context.context_id, context);
      if (context.type !== nativeType) add(errors, `${contextPath}.type changes model-native graph semantics.`);
      if (!isInteger(context.index) || context.index < 0) add(errors, `${contextPath}.index must be non-negative.`);
      if (nativeType === 'scale' && (!isInteger(context.layer) || context.layer < 0)) add(errors, `${contextPath}.layer is required for scale contexts.`);
      if ((nativeType === 'window' || nativeType === 'global_graph') && context.layer !== undefined) add(errors, `${contextPath}.layer is not valid for ${nativeType} contexts.`);
      if (context.layer !== undefined && (!isInteger(context.layer) || context.layer < 0)) add(errors, `${contextPath}.layer must be a non-negative integer when present.`);
      if (context.node_count !== variables.length) add(errors, `${contextPath}.node_count differs from dataset variables.`);
      const graphs = requireRecord(context.graphs, `${contextPath}.graphs`, errors);
      if (graphs) {
        if (Object.keys(graphs).length === 0) add(errors, `${contextPath}.graphs must be non-empty.`);
        for (const [name, graph] of Object.entries(graphs)) {
          if (validateTensor(graph, `${contextPath}.graphs.${name}`, errors) && isRecord(graph)) {
            const shape = graph.shape;
            const axes = graph.axis_order;
            if (!Array.isArray(shape) || shape[0] !== variables.length || shape[1] !== variables.length || shape.length !== 2) {
              add(errors, `${contextPath}.graphs.${name} is not a variable-by-variable matrix.`);
            }
            if (!Array.isArray(axes) || axes[0] !== 'source_node' || axes[1] !== 'target_node') {
              add(errors, `${contextPath}.graphs.${name} has incompatible axes.`);
            }
          }
        }
      }
      if (!isRecord(context.native_metadata)) add(errors, `${contextPath}.native_metadata must be an object.`);
    });
    contextsBySample.set(sample.sample_id, contextMap);
  });

  const plan = requireRecord(root.audit_plan, 'session.audit_plan', errors);
  if (plan) {
    requireFields(plan, ['split', 'sample_indices', 'relation_count', 'local_scope', 'broader_context_scope'], 'session.audit_plan', errors);
    if (!Array.isArray(plan.sample_indices) || plan.sample_indices.length !== sampleOrder.length ||
      plan.sample_indices.some((value, index) => value !== sampleOrder[index])) {
      add(errors, 'session.audit_plan.sample_indices does not match exported samples.');
    }
  }

  const relations = Array.isArray(root.relations) ? root.relations : [];
  if (!Array.isArray(root.relations)) add(errors, 'session.relations must be an array.');
  const relationById = new Map<string, Record<string, unknown>>();
  relations.forEach((value, relationPosition) => {
    const path = `session.relations[${relationPosition}]`;
    const relation = requireRecord(value, path, errors);
    if (!relation) return;
    requireFields(relation, [
      'relation_id', 'sample_id', 'source', 'target', 'source_name', 'target_name',
      'native_occurrences', 'evidence_ids',
    ], path, errors);
    if (typeof relation.relation_id !== 'string' || !relation.relation_id || relationById.has(relation.relation_id)) {
      add(errors, `${path}.relation_id must be unique.`);
      return;
    }
    relationById.set(relation.relation_id, relation);
    if (typeof relation.sample_id !== 'string' || !sampleById.has(relation.sample_id)) add(errors, `${path} references an unknown sample.`);
    const source = relation.source;
    const target = relation.target;
    if (!isInteger(source) || !isInteger(target) || source < 0 || target < 0 || source >= variables.length || target >= variables.length || source === target) {
      add(errors, `${path} has an invalid directed non-self relation.`);
    } else if (relation.source_name !== variables[source] || relation.target_name !== variables[target]) {
      add(errors, `${path} source/target names differ from dataset variables.`);
    }
    if (!Array.isArray(relation.native_occurrences)) add(errors, `${path}.native_occurrences must be an array.`);
    else relation.native_occurrences.forEach((occurrenceValue, occurrencePosition) => {
      const occurrence = requireRecord(occurrenceValue, `${path}.native_occurrences[${occurrencePosition}]`, errors);
      if (!occurrence) return;
      if (typeof relation.sample_id === 'string' && !contextsBySample.get(relation.sample_id)?.has(String(occurrence.context_id))) {
        add(errors, `${path}.native_occurrences[${occurrencePosition}] references an unknown context.`);
      }
      if (typeof occurrence.weight !== 'number' || !Number.isFinite(occurrence.weight)) add(errors, `${path} has a non-finite occurrence weight.`);
    });
    if (!Array.isArray(relation.evidence_ids) || relation.evidence_ids.some(id => typeof id !== 'string')) {
      add(errors, `${path}.evidence_ids must be a string array.`);
    }
  });
  if (plan && plan.relation_count !== relations.length) add(errors, 'session.audit_plan.relation_count does not match relations.');

  const evidence = Array.isArray(root.evidence_records) ? root.evidence_records : [];
  if (!Array.isArray(root.evidence_records)) add(errors, 'session.evidence_records must be an array.');
  const evidenceIds = new Set<string>();
  const evidenceByRelation = new Map<string, Set<string>>();
  const exactKeys = new Set<string>();
  let localCount = 0;
  let broaderCount = 0;
  let localSupported = 0;
  let broaderSupported = 0;
  let notExposedCount = 0;
  let missingCount = 0;
  evidence.forEach((value, evidencePosition) => {
    const path = `session.evidence_records[${evidencePosition}]`;
    const record = requireRecord(value, path, errors);
    if (!record) return;
    requireFields(record, ['evidence_id', 'relation_id', 'selection', 'status', 'reason', 'value'], path, errors);
    if (typeof record.evidence_id !== 'string' || !record.evidence_id || evidenceIds.has(record.evidence_id)) {
      add(errors, `${path}.evidence_id must be unique.`);
      return;
    }
    evidenceIds.add(record.evidence_id);
    if (typeof record.relation_id !== 'string' || !relationById.has(record.relation_id)) {
      add(errors, `${path} references an unknown relation.`);
      return;
    }
    if (!evidenceByRelation.has(record.relation_id)) evidenceByRelation.set(record.relation_id, new Set());
    evidenceByRelation.get(record.relation_id)!.add(record.evidence_id);
    const relation = relationById.get(record.relation_id)!;
    const selection = requireRecord(record.selection, `${path}.selection`, errors);
    if (selection) {
      requireFields(selection, [
        'model', 'dataset', 'sample_id', 'sample_index', 'context_type', 'context_id', 'context_index',
        'source', 'target', 'source_name', 'target_name', 'scope',
      ], `${path}.selection`, errors);
      const sample = sampleById.get(String(relation.sample_id));
      const expected: Record<string, unknown> = {
        model: modelName, dataset: dataset?.name, sample_id: relation.sample_id,
        sample_index: sample?.sample_index, source: relation.source, target: relation.target,
        source_name: relation.source_name, target_name: relation.target_name,
      };
      for (const [field, expectedValue] of Object.entries(expected)) {
        if (selection[field] !== expectedValue) add(errors, `${path}.selection.${field} disagrees with its relation/session.`);
      }
      if (selection.scope === 'local') {
        localCount += 1;
        if (selection.context_type !== nativeType || selection.context_index === 'all_applicable' ||
          !contextsBySample.get(String(relation.sample_id))?.has(String(selection.context_id))) {
          add(errors, `${path} does not resolve to an exact native local context.`);
        }
      } else if (selection.scope === 'broader_context') {
        broaderCount += 1;
        const expectedSet = nativeType === 'window' ? 'window_set' : nativeType === 'scale' ? 'scale_set' : null;
        const invalidKnownSet = expectedSet !== null && selection.context_type !== expectedSet;
        if (typeof selection.context_type !== 'string' || !selection.context_type || selection.context_type === nativeType ||
          invalidKnownSet || selection.context_index !== 'all_applicable') {
          add(errors, `${path} has an invalid broader-context selection.`);
        }
      } else add(errors, `${path}.selection.scope is unsupported.`);
      const exactKey = JSON.stringify([
        selection.model, selection.dataset, selection.sample_id, selection.sample_index,
        selection.context_type, selection.context_id, selection.context_index, selection.layer ?? null,
        selection.source, selection.target, selection.source_name, selection.target_name, selection.scope,
      ]);
      if (exactKeys.has(exactKey)) add(errors, `${path} duplicates an exact evidence selection.`);
      exactKeys.add(exactKey);
    }

    if (record.status === 'missing' || record.status === 'unavailable') {
      missingCount += 1;
      if (record.value !== null || typeof record.reason !== 'string' || !record.reason) {
        add(errors, `${path} missing/unavailable evidence requires value=null and a reason.`);
      }
      return;
    }
    if (record.status === 'not_exposed') {
      notExposedCount += 1;
      if (typeof record.reason !== 'string' || !record.reason) add(errors, `${path} not_exposed evidence requires a reason.`);
    } else if (record.status !== 'available' || record.reason !== null) {
      add(errors, `${path} has inconsistent status/reason.`);
    }
    const payload = requireRecord(record.value, `${path}.value`, errors);
    if (!payload) return;
    requireFields(payload, [
      'baseline_output_ref', 'intervention_output', 'metrics', 'statistics', 'metric_status',
      'controls', 'graph_effect', 'diagnostic_localization', 'limitations', 'provenance',
    ], `${path}.value`, errors);
    if (payload.baseline_output_ref !== `${relation.sample_id}:baseline`) add(errors, `${path} has an unresolved baseline reference.`);
    validateNullableTensor(payload.intervention_output, `${path}.value.intervention_output`, errors);
    validateMetricMap(payload.metrics, `${path}.value.metrics`, errors);
    validateMetricMap(payload.statistics, `${path}.value.statistics`, errors);
    validateControls(payload.controls, `${path}.value.controls`, errors);
    if (!isRecord(payload.graph_effect)) add(errors, `${path}.value.graph_effect must be an object.`);
    if (!isRecord(payload.provenance)) add(errors, `${path}.value.provenance must be an object.`);
    if (!Array.isArray(payload.limitations) || payload.limitations.some(item => typeof item !== 'string')) {
      add(errors, `${path}.value.limitations must be a string array.`);
    }
    const statistics = isRecord(payload.statistics) ? payload.statistics : null;
    const bh = statistics?.bh_adjusted_p;
    if (typeof bh === 'number' && bh < .05 && selection) {
      if (selection.scope === 'local') localSupported += 1;
      else broaderSupported += 1;
    }
  });

  for (const [relationId, relation] of relationById) {
    const declared = Array.isArray(relation.evidence_ids) ? relation.evidence_ids : [];
    const actual = evidenceByRelation.get(relationId) ?? new Set();
    if (new Set(declared).size !== declared.length || declared.length !== actual.size || declared.some(id => !actual.has(String(id)))) {
      add(errors, `session relation ${relationId} does not reference exactly its evidence records.`);
    }
  }

  const summary = requireRecord(root.evidence_summary, 'session.evidence_summary', errors);
  if (summary) {
    requireFields(summary, [
      'local_case_count', 'broader_context_case_count', 'local_bh_supported_count',
      'broader_context_bh_supported_count', 'negative_evidence_preserved',
    ], 'session.evidence_summary', errors);
    const expectedCounts: Record<string, number> = {
      local_case_count: localCount,
      broader_context_case_count: broaderCount,
      local_bh_supported_count: localSupported,
      broader_context_bh_supported_count: broaderSupported,
    };
    if ('not_exposed_case_count' in summary) expectedCounts.not_exposed_case_count = notExposedCount;
    if ('missing_case_count' in summary) expectedCounts.missing_case_count = missingCount;
    for (const [field, expected] of Object.entries(expectedCounts)) {
      if (summary[field] !== expected) add(errors, `session.evidence_summary.${field} does not match stored records.`);
    }
    if (summary.negative_evidence_preserved !== true) add(errors, 'session must preserve negative evidence.');
  }

  const crossRun = requireRecord(root.cross_run_evidence, 'session.cross_run_evidence', errors);
  if (crossRun) {
    requireFields(crossRun, ['status', 'value', 'reason'], 'session.cross_run_evidence', errors);
    if (crossRun.status === 'missing' || crossRun.status === 'not_evaluated' || crossRun.status === 'unavailable') {
      if (crossRun.value !== null || typeof crossRun.reason !== 'string' || !crossRun.reason) {
        add(errors, 'session.cross_run_evidence missing state requires value=null and a reason.');
      }
    }
  }
  const provenance = requireRecord(root.provenance, 'session.provenance', errors);
  if (provenance) {
    requireFields(provenance, [
      'session_generation_run_id', 'validation', 'config_sha256', 'source_runs', 'commands',
      'environment', 'code_references', 'source_artifacts',
    ], 'session.provenance', errors);
    validateSha(provenance.config_sha256, 'session.provenance.config_sha256', errors);
    const validation = requireRecord(provenance.validation, 'session.provenance.validation', errors);
    if (validation) {
      requireFields(validation, ['kind', 'status', 'report_sha256'], 'session.provenance.validation', errors);
      if (validation.status !== 'passed' || !['adapter_preflight', 'artifact_roundtrip_validation'].includes(String(validation.kind))) {
        add(errors, 'session.provenance.validation is incompatible.');
      }
      validateSha(validation.report_sha256, 'session.provenance.validation.report_sha256', errors);
    }
    const generator = metadata && isRecord(metadata.generator) ? metadata.generator : null;
    if (generator?.run_id !== provenance.session_generation_run_id) add(errors, 'session generation run IDs disagree.');
  }
  if (!Array.isArray(root.limitations) || root.limitations.some(item => typeof item !== 'string')) {
    add(errors, 'session.limitations must be a string array.');
  }

  if (errors.length) return { valid: false, session: null, errors };
  return { valid: true, session: input as AuditSession, errors: [] };
}

export function parseAuditSession(text: string): AuditSessionValidationResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    return {
      valid: false,
      session: null,
      errors: [`The selected file is not valid JSON: ${error instanceof Error ? error.message : String(error)}`],
    };
  }
  return validateAuditSession(parsed);
}

export function tensorMatrix(tensor: AuditTensor): number[][] {
  return tensor.values as number[][];
}

export function findExactEvidence(
  session: AuditSession,
  selection: {
    sample: number;
    contextType: NativeContextType;
    contextIndex: number;
    source: number;
    target: number;
  },
  scope: EvidenceScope,
): AuditEvidenceRecord | undefined {
  return session.evidence_records.find(record => {
    const exact = record.selection;
    if (exact.sample_index !== selection.sample || exact.source !== selection.source || exact.target !== selection.target || exact.scope !== scope) return false;
    if (scope === 'broader_context') return exact.context_index === 'all_applicable';
    return exact.context_type === selection.contextType && exact.context_index === selection.contextIndex;
  });
}
