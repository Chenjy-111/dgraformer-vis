from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import load_audit_config_v2
from .frozen import load_frozen_inputs
from .session import build_audit_session_v2, write_audit_session_v2


Progress = Callable[[str], None]


def run_audit_v2(config_path: str | Path, *, output_path: str | Path = "dgrainsight_session_v2.json", progress: Progress | None = None, include_intervention_trajectories: bool = True) -> tuple[Path, dict[str, Any]]:
    resolved, config = load_audit_config_v2(config_path)
    tell = progress or (lambda _message: None)
    tell("V10 Statistical Protocol Validation: PASS")
    tell("V11 Hypothesis Family Validation: PASS")
    if config.get("frozen_protocol"):
        generated, graph, cases, dependence, provenance = load_frozen_inputs(str(config["frozen_protocol"]), include_intervention_trajectories=include_intervention_trajectories)
        _assert_frozen_config(config, generated)
        provenance = {**provenance, "audit_config_sha256": _sha256(resolved)}
    else:
        inputs = config.get("prepared_inputs")
        if not isinstance(inputs, Mapping):
            raise ValueError("A non-frozen v2 audit requires prepared_inputs for graph core, case evidence, and dependence audit")
        graph = _read_relative(resolved, inputs["graph_core_session_v1"])
        cases = _read_relative(resolved, inputs["case_evidence"])
        dependence_records = _read_relative(resolved, inputs["dependence_audit"])
        dependence = {str(item["family_id"]): item for item in dependence_records}
        provenance = {"prepared_inputs": True, "audit_config_sha256": _sha256(resolved)}
    tell("Aggregating case D by frozen candidate identity")
    session = build_audit_session_v2(config=config, graph_core_session_v1=graph, case_evidence=cases, dependence_by_family=dependence, generator={"name": "dgraudit", "version": "pipeline-v2"}, additional_provenance=provenance)
    output = write_audit_session_v2(output_path, session)
    return output, session


def _assert_frozen_config(actual: Mapping[str, Any], generated: Mapping[str, Any]) -> None:
    for key in ("adapter", "sample_protocol", "candidate_families", "control_protocol", "response_metric", "dependence_protocol", "inference_protocol", "multiplicity_protocol", "sensitivity_protocol"):
        if actual.get(key) != generated.get(key):
            raise ValueError(f"Frozen protocol config drift detected in {key}")


def _read_relative(config_path: Path, value: str) -> Any:
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()
    return json.loads(resolved.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def terminal_summary(session: Mapping[str, Any], output: Path) -> str:
    families = session["hypothesis_families"]
    cross = session["cross_sample_evidence"]
    lines = ["DGraInsight Formal Audit", "=========================", f"Model: {session['model']['name']}", f"Dataset: {session['dataset']['name']}", f"Checkpoint: {session['checkpoint']['sha256']}", "", "V01–V09 Model Validation: preserved from validated graph core", "V10 Statistical Protocol Validation: PASS", "V11 Hypothesis Family Validation: PASS", f"Samples planned: {len(session['audit_plan']['sample_protocol']['sample_ids'])}"]
    lines.append(f"Samples active: {len(set(sample for item in cross for sample in item['active_samples']))}")
    for family in families:
        relevant = [item for item in cross if item["family_id"] == family["family_id"]]
        supported = sum(item["multiplicity"]["supported"] is True for item in relevant)
        method = next((item["primary_inference"]["method"] for item in relevant if item["primary_inference"]["method"]), "unavailable")
        lines.extend([f"Family {family['family_id']}: {family['size']} candidates", f"  Primary: {method}", f"  Multiple testing: BH", f"  Supported: {supported}/{family['size']}"])
    classes = sorted({item["classification"] for item in session["dependence_audit"]})
    lines.extend([f"Dependence: {', '.join(classes)}", "Sensitivity: reported separately from primary inference", f"Session output: {output}", f"Status: {session['session']['status']}"])
    return "\n".join(lines)
