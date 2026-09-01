from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Type

from dgraudit.adapters import AdapterCapabilities, DynamicGraphForecastAdapter


CUSTOM_ADAPTER_SENTINEL = "custom"


class CustomAdapterLoadError(ValueError):
    """Author-facing custom adapter loading failure."""

    def __init__(self, code: str, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.code = code
        self.cause = cause


@dataclass(frozen=True)
class LoadedCustomAdapter:
    adapter_class: Type[DynamicGraphForecastAdapter]
    module: str
    class_name: str
    adapter_id: str
    adapter_name: str
    model_name: str
    adapter_version: str | None
    capabilities: AdapterCapabilities


def load_custom_adapter_class(
    declaration: Mapping[str, Any], source_root: Path
) -> LoadedCustomAdapter:
    """Import one explicitly named local adapter. No module scanning or fallback occurs."""

    module_name = declaration.get("module")
    class_name = declaration.get("class")
    if not isinstance(module_name, str) or not module_name.strip():
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_MODULE_INVALID",
            "Custom adapter module must be an explicit non-empty Python module name.",
        )
    if not isinstance(class_name, str) or not class_name.strip():
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_CLASS_INVALID",
            "Custom adapter class must be an explicit non-empty class name.",
        )
    source = str(source_root.resolve())
    if source not in sys.path:
        sys.path.insert(0, source)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_IMPORT_FAILED",
            f"Custom adapter module could not be imported: {module_name}.",
            cause=exc,
        ) from exc
    adapter_class = getattr(module, class_name, None)
    if adapter_class is None:
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_CLASS_NOT_FOUND",
            f"Adapter class not found: {class_name} in {module_name}.",
        )
    if not inspect.isclass(adapter_class) or not issubclass(adapter_class, DynamicGraphForecastAdapter):
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_TYPE_INVALID",
            "Adapter does not satisfy DGraInsight adapter type requirements.",
        )
    if inspect.isabstract(adapter_class):
        missing = sorted(getattr(adapter_class, "__abstractmethods__", ()))
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_CONTRACT_INCOMPLETE",
            "Adapter contract incomplete. Missing implementations: " + ", ".join(missing),
        )
    capabilities = getattr(adapter_class, "CAPABILITIES", None)
    if not isinstance(capabilities, AdapterCapabilities):
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_CAPABILITIES_INVALID",
            "Custom adapter must declare CAPABILITIES as AdapterCapabilities.",
        )
    if not capabilities.supports_quick_inspection or not capabilities.supports_graph_override:
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_CAPABILITIES_INVALID",
            "Custom adapter capabilities do not support Quick Inspection graph overrides.",
        )
    adapter_id = getattr(adapter_class, "ADAPTER_ID", "")
    model_name = getattr(adapter_class, "MODEL_NAME", "")
    if not isinstance(adapter_id, str) or not adapter_id.strip() or adapter_id == CUSTOM_ADAPTER_SENTINEL:
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_ID_INVALID",
            "Custom adapter ADAPTER_ID must be a non-empty stable id other than 'custom'.",
        )
    if not isinstance(model_name, str) or not model_name.strip():
        raise CustomAdapterLoadError(
            "CUSTOM_ADAPTER_MODEL_INVALID",
            "Custom adapter MODEL_NAME must be a non-empty model identity.",
        )
    return LoadedCustomAdapter(
        adapter_class=adapter_class,
        module=module_name,
        class_name=class_name,
        adapter_id=adapter_id,
        adapter_name=class_name,
        model_name=model_name,
        adapter_version=getattr(adapter_class, "ADAPTER_VERSION", None),
        capabilities=capabilities,
    )
