import time

import streamlit as st

from src.config import settings
from src.event_listener import EventListener
from src.gateway_client import GatewayClient
from src.storage_client import StorageClient
from src.ui.job_list import render_job_list
from src.ui.pipeline_view import render_pipeline_view
from src.ui.upload_form import render_upload_form

# page config
st.set_page_config(
    page_title=settings.page_title,
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# custom css for better aesthetics
st.markdown(
    """
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stButton button {
        border-radius: 8px;
    }
    .element-container {
        margin-bottom: 0.5rem;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    h1 {
        padding-bottom: 1rem;
        border-bottom: 2px solid #f0f2f6;
        margin-bottom: 2rem;
    }
    h2, h3 {
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


# initialize clients (cached)
@st.cache_resource
def get_event_listener():
    """get or create event listener singleton"""
    listener = EventListener()
    listener.start_listening()
    return listener


@st.cache_resource
def get_storage_client():
    """get or create storage client singleton"""
    return StorageClient()


@st.cache_resource
def get_gateway_client():
    """get or create gateway client singleton"""
    return GatewayClient(settings.gateway_url)


# get clients
listener = get_event_listener()
storage = get_storage_client()
gateway = get_gateway_client()

# main title
st.title("🔍 OCR Pipeline Visualizer")

# sidebar
with st.sidebar:
    st.header("Jobs")

    # stats in compact grid
    stats = listener.get_stats()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total", stats.get("total", 0))
        st.metric("Processing", stats.get("processing", 0), delta=None, help="⚙️")
    with col2:
        st.metric("Queued", stats.get("queued", 0), delta=None, help="⏳")
        st.metric("Completed", stats.get("completed", 0), delta=None, help="✅")

    st.divider()

    # filters
    status_filter = st.selectbox(
        "Filter",
        ["all", "processing", "queued", "completed", "failed"],
        index=0,
        label_visibility="collapsed",
    )

    # get jobs
    jobs = listener.get_jobs(
        limit=settings.max_jobs_display,
        status=None if status_filter == "all" else status_filter,
    )

    # render job list
    selected_job_id = st.session_state.get("selected_job_id")
    new_selected = render_job_list(jobs, selected_job_id)

    if new_selected:
        st.session_state.selected_job_id = new_selected
        st.session_state.just_uploaded = False
        st.rerun()

    st.divider()

    # auto refresh
    auto_refresh = st.toggle("Auto Refresh", value=True)
    if auto_refresh:
        refresh_interval = st.slider(
            "Interval (s)",
            min_value=1,
            max_value=10,
            value=settings.auto_refresh_interval,
            label_visibility="collapsed",
        )
        st.caption(f"Refreshing every {refresh_interval}s")
    else:
        refresh_interval = settings.auto_refresh_interval

# main content area
main_col1, main_col2 = st.columns([1, 2], gap="large")

with main_col1, st.container():
    st.subheader("📤 Upload")

    uploaded = render_upload_form(gateway)

    if uploaded or st.session_state.get("just_uploaded", False):
        st.success("Job created, check panel →")

with main_col2, st.container():
    st.subheader("🔍 Pipeline")

    if "selected_job_id" not in st.session_state:
        st.info("Select job from sidebar or upload image")

        # recent jobs overview
        if jobs:
            st.write("")
            st.caption("**Recent Activity**")

            table_data = []
            for job in jobs[:8]:
                table_data.append(
                    {
                        "ID": job["id"][:8],
                        "Status": job.get("status", "—"),
                        "Result": job.get("resultType", "—")
                        if job.get("status") == "completed"
                        else "—",
                        "Time": job.get("createdAt", "—").split("T")[1][:8]
                        if "createdAt" in job
                        else "—",
                    }
                )

            st.dataframe(table_data, use_container_width=True, hide_index=True, height=280)
    else:
        job = listener.get_job(st.session_state.selected_job_id)

        if not job:
            st.warning("⏳ Waiting for job to appear in system...")

            if st.button("Clear Selection", use_container_width=True):
                del st.session_state.selected_job_id
                if "just_uploaded" in st.session_state:
                    del st.session_state.just_uploaded
                st.rerun()
        else:
            if "just_uploaded" in st.session_state:
                st.session_state.just_uploaded = False

            render_pipeline_view(job, storage)

# auto refresh
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
