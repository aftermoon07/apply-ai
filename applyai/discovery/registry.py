"""Registry for Discovery Adapters."""

from typing import Type, Dict
from applyai.discovery.base import DiscoveryAdapter

_REGISTRY: Dict[str, Type[DiscoveryAdapter]] = {}

def register_adapter(adapter_type: str, cls: Type[DiscoveryAdapter]) -> None:
    """Register a new discovery adapter class."""
    _REGISTRY[adapter_type] = cls

def get_adapter_class(adapter_type: str) -> Type[DiscoveryAdapter]:
    """Retrieve an adapter class by its type name."""
    cls = _REGISTRY.get(adapter_type)
    if not cls:
        raise ValueError(f"No discovery adapter registered for type: '{adapter_type}'")
    return cls

# Import adapters here to run their registration logic
import applyai.discovery.adapters.mock  # noqa
