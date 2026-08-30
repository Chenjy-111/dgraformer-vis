"""Reproducible offline audit utilities for DGraInsight.

Adapter imports are lazy so the validation CLI can report a missing Torch
runtime as a structured preflight failure instead of crashing at package import.
"""

from typing import Any

__all__ = ["DGraFormerAdapter", "DynamicGraphForecastAdapter", "MSGNetAdapter"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .adapters import DGraFormerAdapter, DynamicGraphForecastAdapter, MSGNetAdapter

        return {
            "DGraFormerAdapter": DGraFormerAdapter,
            "DynamicGraphForecastAdapter": DynamicGraphForecastAdapter,
            "MSGNetAdapter": MSGNetAdapter,
        }[name]
    raise AttributeError(name)
