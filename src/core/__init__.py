"""Core abstractions: collectors, notifiers, and the orchestration pipeline."""

from src.core.collectors import (
    BaseCollector,
    collector_registry,
    register_collector,
)
from src.core.notifiers import (
    BaseNotifier,
    NotificationResult,
    notifier_registry,
    register_notifier,
)
from src.core.pipeline import (
    PipelineResult,
    load_plugins,
    run_collector,
    run_pipeline,
)

__all__ = [
    "BaseCollector",
    "BaseNotifier",
    "NotificationResult",
    "PipelineResult",
    "collector_registry",
    "load_plugins",
    "notifier_registry",
    "register_collector",
    "register_notifier",
    "run_collector",
    "run_pipeline",
]
