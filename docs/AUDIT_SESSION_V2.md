# Portable Audit Session v2

Session v2 is the only current portable session contract. Its JSON Schema is `schemas/dgrainsight_audit_session_v2.schema.json`.

The document contains immutable model/dataset/checkpoint identity, the frozen audit plan, samples and native graph contexts, descriptive case evidence, candidate relations, hypothesis families, cross-sample/test inference, dependence audit, validation reports, provenance, and limitations.

Case evidence stores the focal response, every unique eligible control identity/response, and `D`. Its `formal_inference` is always `not_evaluated` with null p/q values. Formal raw p-values and BH-adjusted q-values exist only in candidate-level `cross_sample_evidence` and are linked to exactly one frozen family.

Validate a file with:

```bash
python -m dgraudit validate-session dgrainsight_session_v2.json
```

The Python semantic validator, JSON Schema validator, and TypeScript browser validator all fail on malformed tensors, invalid references, duplicated controls, imputed inactive units, invalid p/q values, or case-level formal inference.
