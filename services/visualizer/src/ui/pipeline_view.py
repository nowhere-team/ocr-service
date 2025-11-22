import re

import streamlit as st

from ..animator import PipelineAnimator
from ..storage_client import StorageClient
from .utils import format_duration, format_timestamp, get_status_emoji


def _clean_step_name(step: str) -> str:
    """extract clean step name without numeric prefix"""
    match = re.match(r"^\d+_(.+)$", step)
    if match:
        return match.group(1).replace("_", " ").title()
    return step.replace("_", " ").title()


def render_pipeline_view(job: dict, storage: StorageClient):
    """render pipeline visualization for a job"""
    job_id = job["id"]
    status = job.get("status", "unknown")

    header_col1, header_col2, header_col3 = st.columns([3, 1, 1])

    with header_col1:
        st.markdown(f"### {get_status_emoji(status)} `{job_id[:16]}...`")

    with header_col2:
        st.metric("Status", status.title())

    with header_col3:
        if status == "completed":
            processing_time = job.get("processingTime")
            st.metric("Time", format_duration(processing_time))
        elif status == "queued":
            position = job.get("position", 0)
            st.metric("Position", position)

    st.write("")

    with st.expander("Metadata", expanded=False):
        meta_col1, meta_col2 = st.columns(2)

        with meta_col1:
            st.caption("**Recognition ID**")
            st.code(job_id, language=None)
            st.caption("**Image ID**")
            st.code(job.get("imageId", "—"), language=None)

        with meta_col2:
            st.caption("**Created**")
            st.text(format_timestamp(job.get("createdAt")))

            if job.get("sourceService"):
                st.caption("**Source**")
                st.text(f"{job.get('sourceService')} / {job.get('sourceReference', '—')}")

    stages = job.get("stages", [])

    if not stages and status in ["queued", "processing"]:
        st.info("⏳ Processing, stages will appear soon...")
        return

    if stages:
        st.write("")

        stage_header_col1, stage_header_col2 = st.columns([3, 1])

        with stage_header_col1:
            st.markdown("#### Pipeline Stages")

        with stage_header_col2:
            if st.button("🎬 Create Animation", use_container_width=True, type="secondary"):
                st.session_state.show_animation_controls = True

        if st.session_state.get("show_animation_controls", False):
            with st.expander("⚙️ Animation Settings", expanded=True):
                anim_col1, anim_col2, anim_col3 = st.columns(3)

                with anim_col1:
                    width = st.slider("Width (px)", 400, 1200, 800, 50)

                with anim_col2:
                    duration = st.slider("Duration per Frame (sec)", 0.3, 3.0, 1.0, 0.1)

                with anim_col3:
                    add_labels = st.checkbox("Add Labels", value=True)

                create_col1, create_col2 = st.columns([1, 1])

                with create_col1:
                    if st.button("Generate", type="primary", use_container_width=True):
                        try:
                            with st.spinner("Creating animation..."):
                                animator = PipelineAnimator()

                                frames = animator.create_slideshow_frames(
                                    stages=stages,
                                    storage_client=storage,
                                    width=width,
                                    add_labels=add_labels,
                                )

                                if frames:
                                    gif_bytes = animator.create_gif(
                                        frames=frames, duration_per_frame=duration, loop=True
                                    )

                                    st.session_state.animation_data = gif_bytes
                                    st.session_state.animation_filename = (
                                        f"{job_id[:8]}_pipeline.gif"
                                    )
                                    st.success(f"✅ Created {len(frames)} frames")
                                else:
                                    st.error("Failed to load frames")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

                with create_col2:
                    if st.button("Close", use_container_width=True):
                        st.session_state.show_animation_controls = False
                        if "animation_data" in st.session_state:
                            del st.session_state.animation_data
                        if "animation_filename" in st.session_state:
                            del st.session_state.animation_filename
                        st.rerun()

                if "animation_data" in st.session_state:
                    st.write("")
                    st.image(st.session_state.animation_data, caption="Preview")

                    st.download_button(
                        label="⬇️ Download GIF",
                        data=st.session_state.animation_data,
                        file_name=st.session_state.animation_filename,
                        mime="image/gif",
                        use_container_width=True,
                    )

        st.write("")

        if len(stages) > 0:
            tab_names = [_clean_step_name(stage["step"]) for stage in stages]
            tabs = st.tabs(tab_names)

            for tab, stage in zip(tabs, stages, strict=False):
                with tab:
                    render_stage(stage, storage)

    if status == "completed":
        st.write("")
        st.markdown("#### Result")

        result_type = job.get("resultType")

        if result_type == "text":
            text_data = job.get("text", {})

            res_col1, res_col2, res_col3 = st.columns(3)
            with res_col1:
                st.metric("Engine", text_data.get("engine", "—"))
            with res_col2:
                confidence = text_data.get("confidence", 0)
                st.metric("Confidence", f"{confidence:.1%}")
            with res_col3:
                aligned = text_data.get("aligned", False)
                st.metric("Aligned", "✓" if aligned else "✗")

            st.text_area(
                "Text",
                text_data.get("raw", ""),
                height=200,
                disabled=True,
                label_visibility="collapsed",
            )

        elif result_type == "qr":
            qr_data = job.get("qr", {})

            st.info(f"**Format:** {qr_data.get('format', 'unknown').upper()}")
            st.code(qr_data.get("data", ""), language=None)

    elif status == "failed":
        st.write("")
        st.error(f"**Error:** {job.get('error', 'unknown error')}")


def render_stage(stage: dict, storage: StorageClient):
    """render single pipeline stage"""

    info_col, source_col = st.columns([4, 1])

    with info_col:
        st.caption(stage.get("description", "No description"))

    with source_col:
        source = stage.get("source", "gateway")
        st.caption(f"*{source}*")

    metadata = stage.get("metadata", {})
    if metadata:
        with st.expander("Details", expanded=False):
            for key, value in metadata.items():
                st.text(f"{key}: {value}")

    st.write("")

    image_key = stage.get("imageKey")
    if image_key:
        try:
            with st.spinner("Loading..."):
                image = storage.get_image(image_key)

            if image:
                st.image(image, width=800)
            else:
                st.warning("Failed to load image")

        except Exception as e:
            st.error(f"Error: {str(e)}")
    else:
        st.info("No image available")
