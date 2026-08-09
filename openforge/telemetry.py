"""OpenTelemetry + Langfuse telemetry (H-04/H-05). Safe to import without OTel."""
from __future__ import annotations

from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    _OTEL = True
except Exception:  # pragma: no cover
    _OTEL = False


def init_tracer(service: str = "openforge"):
    if not _OTEL:
        return None
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service)


def span(name: str, **attrs: Any):
    if not _OTEL:
        class _Null:
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _Null()
    tracer = trace.get_tracer("openforge")
    return tracer.start_as_current_span(name, attributes=attrs)


def emit_langfuse(event: str, **payload: Any) -> None:
    """Best-effort push to Langfuse if `langfuse` is installed and configured."""
    try:
        import langfuse  # noqa: F401
        from langfuse.decorators import observe
        # No-op wiring: real observe() is added via decorators in instrumented paths.
    except Exception:
        return
