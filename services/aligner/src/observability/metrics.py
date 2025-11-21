from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# counters
alignment_requests_total = Counter(
    "aligner_alignment_requests_total",
    "total number of alignment requests",
    ["status"],
)

alignment_errors_total = Counter(
    "aligner_alignment_errors_total",
    "total number of alignment errors",
    ["error_type"],
)

# histograms
alignment_duration_seconds = Histogram(
    "aligner_alignment_duration_seconds",
    "alignment processing duration in seconds",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

image_size_bytes = Histogram(
    "aligner_image_size_bytes",
    "processed image size in bytes",
    buckets=[1024, 10240, 102400, 1048576, 5242880, 10485760],
)

# gauges
active_alignments = Gauge(
    "aligner_active_alignments", "number of currently active alignment requests"
)


def metrics_endpoint() -> Response:
    """prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def record_request(status: str) -> None:
    """record alignment request"""
    alignment_requests_total.labels(status=status).inc()


def record_error(error_type: str) -> None:
    """record alignment error"""
    alignment_errors_total.labels(error_type=error_type).inc()


def record_duration(duration: float) -> None:
    """record alignment duration"""
    alignment_duration_seconds.observe(duration)


def record_image_size(size: int) -> None:
    """record image size"""
    image_size_bytes.observe(size)
