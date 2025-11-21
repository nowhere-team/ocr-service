from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ..config import settings
from ..logger import get_logger

logger = get_logger(__name__)


def configure_telemetry() -> None:
    """configure opentelemetry with otlp exporters"""
    if not settings.enable_telemetry:
        logger.info("telemetry disabled")
        return

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "service.version": "0.1.0",
        }
    )

    # traces
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otlp_endpoint, insecure=True),
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    logger.info("telemetry configured", otlp_endpoint=settings.otlp_endpoint)


def instrument_app(app) -> None:
    """instrument fastapi app with opentelemetry"""
    if not settings.enable_telemetry:
        return

    FastAPIInstrumentor.instrument_app(app)
    logger.info("fastapi instrumented with opentelemetry")


def get_tracer(name: str):
    """get tracer instance"""
    return trace.get_tracer(name)


def get_meter(name: str):
    """get meter instance"""
    return metrics.get_meter(name)
