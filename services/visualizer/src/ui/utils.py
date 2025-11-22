from datetime import datetime


def format_timestamp(ts: str | None) -> str:
    """format iso timestamp to readable string"""
    if not ts:
        return "—"
    # noinspection PyBroadException
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return "—"


def format_duration(ms: int | None) -> str:
    """format milliseconds to readable duration"""
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        minutes = ms // 60000
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.0f}s"


def get_status_emoji(status: str) -> str:
    """get emoji for job status"""
    emoji_map = {
        "queued": "⏳",
        "processing": "⚙️",
        "completed": "✅",
        "failed": "❌",
    }
    return emoji_map.get(status, "❓")


def get_status_color(status: str) -> str:
    """get color for job status"""
    color_map = {
        "queued": "blue",
        "processing": "orange",
        "completed": "green",
        "failed": "red",
    }
    return color_map.get(status, "gray")
