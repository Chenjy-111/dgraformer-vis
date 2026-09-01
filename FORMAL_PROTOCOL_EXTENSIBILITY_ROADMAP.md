# Formal Protocol Extensibility Roadmap

Adapter Extensibility v1 deliberately stops at generic technical execution and Session v2 Quick
Inspection. The existing frozen DGraFormer and MSGNet formal pipelines remain unchanged.

A future protocol extension may expose a `FormalAuditProtocol` loader only when it can validate:

- predeclared sample/test units and active/inactive rules;
- frozen candidate relations and hypothesis families;
- exact context/scope identity compatible with adapter capabilities;
- all-unique-eligible matched-control rules;
- response metric and candidate-level aggregation;
- dependence classification and compatible primary inference;
- multiplicity family and BH settings;
- sensitivity procedures that do not replace the primary result;
- protocol/config provenance and immutable hashes.

The protocol layer must never modify model forward, while the adapter must never choose statistical
tests or BH families. Until this boundary has a stable external validation contract, a custom adapter
that passes V01–V09 is Quick Inspection ready only. The formal CLI fails closed for `adapter=custom`.
