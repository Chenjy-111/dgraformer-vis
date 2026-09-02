# Development and audit history

This directory preserves dated engineering audits, migration records, release manifests, and implementation reports that support repository provenance but are not part of the current user workflow.

Current installation, audit, and reproduction instructions live in the repository [`README.md`](../../README.md), the [`dgraudit` guide](../../dgraudit/README.md), and the active documents one level above this directory.

## Adapter extensibility records

- [`ADAPTER_CONTRACT_AUDIT.md`](ADAPTER_CONTRACT_AUDIT.md) — audit of the public adapter boundary.
- [`ADAPTER_EXTENSIBILITY_BASELINE.md`](ADAPTER_EXTENSIBILITY_BASELINE.md) — pre-implementation regression baseline.
- [`ADAPTER_EXTENSIBILITY_V1_IMPLEMENTATION_REPORT.md`](ADAPTER_EXTENSIBILITY_V1_IMPLEMENTATION_REPORT.md) — implementation outcome and validation record.
- [`FORMAL_PROTOCOL_EXTENSIBILITY_ROADMAP.md`](FORMAL_PROTOCOL_EXTENSIBILITY_ROADMAP.md) — bounded roadmap beyond adapter-level extensibility.

## Public repository records

- [`DGRAINSIGHT_PUBLIC_REPOSITORY_AUDIT.md`](DGRAINSIGHT_PUBLIC_REPOSITORY_AUDIT.md) — dated public-readiness audit.
- [`DGRAINSIGHT_PUBLIC_UPLOAD_MANIFEST.md`](DGRAINSIGHT_PUBLIC_UPLOAD_MANIFEST.md) — public upload classification and manifest.

## Session v1 retirement records

- [`V1_REMOVAL_DEPENDENCY_AUDIT.md`](V1_REMOVAL_DEPENDENCY_AUDIT.md) — dependency classification performed before removal.
- [`DGRAINSIGHT_V1_REMOVAL_MANIFEST.md`](DGRAINSIGHT_V1_REMOVAL_MANIFEST.md) — removed-file manifest and recovery point.
- [`DGRAINSIGHT_V1_SAFE_REMOVAL_REPORT.md`](DGRAINSIGHT_V1_SAFE_REMOVAL_REPORT.md) — post-removal verification report.

These files are historical records. For current behavior, use the source, tests, Config v2 templates, Session v2 schema, and active documentation.
