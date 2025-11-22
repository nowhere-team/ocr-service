import streamlit as st

from .utils import format_timestamp, get_status_emoji


def render_job_list(jobs: list[dict], selected_job_id: str | None = None) -> str | None:
    """
    render job list in sidebar

    args:
        jobs: list of job dicts
        selected_job_id: currently selected job id

    returns:
        selected job id or none
    """
    if not jobs:
        st.info("No jobs found")
        return None

    status_groups = {
        "processing": [],
        "queued": [],
        "completed": [],
        "failed": [],
    }

    for job in jobs:
        status = job.get("status", "unknown")
        if status in status_groups:
            status_groups[status].append(job)

    selected = None

    for status, group_jobs in status_groups.items():
        if not group_jobs:
            continue

        with st.expander(
            f"{get_status_emoji(status)} {status.title()} ({len(group_jobs)})",
            expanded=(status in ["processing", "queued"]),
        ):
            for job in group_jobs:
                job_id = job["id"]
                short_id = job_id[:8]
                created = format_timestamp(job.get("createdAt"))

                label = f"`{short_id}` · {created}"

                if st.button(
                    label,
                    key=f"job_{job_id}",
                    use_container_width=True,
                    type="primary" if job_id == selected_job_id else "secondary",
                ):
                    selected = job_id

    return selected
