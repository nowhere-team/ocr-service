import re

import streamlit as st

from ..animator import PipelineAnimator
from ..deepseek_client import DeepSeekClient
from ..storage_client import StorageClient
from .utils import format_duration, format_timestamp, get_status_emoji


def _clean_step_name(step: str) -> str:
    """extract clean step name without numeric prefix"""
    match = re.match(r"^\d+_(.+)$", step)
    if match:
        return match.group(1).replace("_", " ").title()
    return step.replace("_", " ").title()


def _get_alignment_mode_badge(stage: dict) -> str | None:
    """extract alignment mode from stage metadata"""
    metadata = stage.get("metadata", {})

    # check for method info in metadata
    if "method" in metadata:
        return metadata["method"]

    # fallback detection based on step description
    description = stage.get("description", "").lower()
    if "neural" in description or "docaligner" in description or "heatmap" in description:
        return "neural"
    elif "opencv" in description or "contour" in description:
        return "classic"

    return None


def render_pipeline_view(job: dict, storage: StorageClient):
    """render pipeline visualization for a job"""
    job_id = job["id"]
    status = job.get("status", "unknown")

    header_col1, header_col2, header_col3 = st.columns([3, 1, 1])
    with header_col1:
        st.markdown(f"### {get_status_emoji(status)} {job_id[:16]}...")
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

        stage_map = {}
        for stage in stages:
            step = stage["step"]
            source = stage.get("source", "gateway")
            if step == "00_original":
                if source == "aligner" or step not in stage_map:
                    stage_map[step] = stage
            elif step not in stage_map:
                stage_map[step] = stage

        unique_stages = list(stage_map.values())
        sorted_stages = sorted(unique_stages, key=lambda x: x.get("timestamp", 0))

        seen_tab_names = set()
        final_stages = []
        for stage in sorted_stages:
            tab_name = _clean_step_name(stage["step"])
            tab_name_lower = tab_name.lower()
            if tab_name_lower not in seen_tab_names:
                final_stages.append(stage)
                seen_tab_names.add(tab_name_lower)

        sorted_stages = final_stages

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
                                    stages=sorted_stages,
                                    storage_client=storage,
                                    width=width,
                                    add_labels=add_labels,
                                )
                                if frames:
                                    gif_bytes = animator.create_gif(
                                        frames=frames, duration_per_frame=duration, loop=True
                                    )
                                    mp4_bytes = animator.create_mp4(
                                        frames=frames,
                                        fps=1.0 / duration,
                                    )
                                    st.session_state.animation_gif = gif_bytes
                                    st.session_state.animation_mp4 = mp4_bytes
                                    st.session_state.animation_filename_base = (
                                        f"{job_id[:8]}_pipeline"
                                    )
                                    st.success(f"✅ Created {len(frames)} frames")
                                else:
                                    st.error("Failed to load frames")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

                with create_col2:
                    if st.button("Close", use_container_width=True):
                        st.session_state.show_animation_controls = False
                        if "animation_gif" in st.session_state:
                            del st.session_state.animation_gif
                        if "animation_mp4" in st.session_state:
                            del st.session_state.animation_mp4
                        if "animation_filename_base" in st.session_state:
                            del st.session_state.animation_filename_base
                        st.rerun()

            if "animation_gif" in st.session_state:
                st.write("")
                st.image(st.session_state.animation_gif, caption="Preview")

                download_col1, download_col2 = st.columns(2)
                with download_col1:
                    st.download_button(
                        label="⬇️ Download GIF",
                        data=st.session_state.animation_gif,
                        file_name=f"{st.session_state.animation_filename_base}.gif",
                        mime="image/gif",
                        use_container_width=True,
                    )
                with download_col2:
                    st.download_button(
                        label="⬇️ Download MP4",
                        data=st.session_state.animation_mp4,
                        file_name=f"{st.session_state.animation_filename_base}.mp4",
                        mime="video/mp4",
                        use_container_width=True,
                    )

        st.write("")

        if len(sorted_stages) > 0:
            tab_names = [_clean_step_name(stage["step"]) for stage in sorted_stages]
            tabs = st.tabs(tab_names)

            for tab, stage in zip(tabs, sorted_stages, strict=False):
                with tab:
                    render_stage(stage, storage)

        if status == "completed":
            st.write("")
            st.markdown("#### Result")

            result_type = job.get("resultType")
            if result_type == "text":
                text_data = job.get("text", {})
                res_col1, res_col2, res_col3, res_col4 = st.columns(4)
                with res_col1:
                    st.metric("Engine", text_data.get("engine", "—"))
                with res_col2:
                    confidence = text_data.get("confidence", 0)
                    st.metric("Confidence", f"{confidence:.1%}")
                with res_col3:
                    aligned = text_data.get("aligned", False)
                    st.metric("Aligned", "✓" if aligned else "✗")
                with res_col4:
                    used_preprocessed = text_data.get("usedPreprocessed", False)
                    version_badge = "📄 preprocessed" if used_preprocessed else "🖼️ warped"
                    st.metric("Version", version_badge)

                raw_text = text_data.get("raw", "")
                st.text_area(
                    "Text",
                    raw_text,
                    height=200,
                    disabled=True,
                    label_visibility="collapsed",
                )

                # deepseek structuring button
                if raw_text:
                    structure_col1, structure_col2 = st.columns([1, 3])
                    with structure_col1:
                        if st.button(
                            "🧠 Структурировать через DeepSeek",
                            use_container_width=True,
                            type="primary",
                        ):
                            st.session_state[f"structure_job_{job_id}"] = True

                    with structure_col2:
                        if st.session_state.get(f"structure_job_{job_id}", False) and st.button(
                            "✕ Закрыть", use_container_width=True
                        ):
                            st.session_state[f"structure_job_{job_id}"] = False
                            if f"structured_data_{job_id}" in st.session_state:
                                del st.session_state[f"structured_data_{job_id}"]
                            st.rerun()

                    if st.session_state.get(f"structure_job_{job_id}", False):
                        if f"structured_data_{job_id}" not in st.session_state:
                            with st.spinner("⏳ Обработка через DeepSeek..."):
                                deepseek = DeepSeekClient()
                                structured = deepseek.structure_text(raw_text)
                                st.session_state[f"structured_data_{job_id}"] = structured

                        structured = st.session_state[f"structured_data_{job_id}"]

                        if "error" in structured:
                            st.error(f"❌ Ошибка: {structured['error']}")
                            if "details" in structured:
                                st.caption(structured["details"])
                        else:
                            _render_structured_result(structured)

            elif result_type == "qr":
                qr_data = job.get("qr", {})
                qr_col1, qr_col2 = st.columns([3, 1])
                with qr_col1:
                    st.info(f"**Format:** {qr_data.get('format', 'unknown').upper()}")
                with qr_col2:
                    found_in_preprocessed = qr_data.get("foundInPreprocessed", False)
                    version_badge = "📄 preprocessed" if found_in_preprocessed else "🖼️ warped"
                    st.caption(f"**found in:** {version_badge}")
                st.code(qr_data.get("data", ""), language=None)

        elif status == "failed":
            st.write("")
            st.error(f"**Error:** {job.get('error', 'unknown error')}")


def _render_structured_result(data: dict):
    """render structured data from deepseek"""
    st.write("")
    st.markdown("##### 📊 структурированные данные")

    # confidence and warnings
    conf_col, warn_col = st.columns([1, 2])
    with conf_col:
        confidence = data.get("confidence", "unknown")
        conf_emoji = {"high": "✅", "medium": "⚠️", "low": "❌"}.get(confidence, "❓")
        conf_labels = {"high": "высокая", "medium": "средняя", "low": "низкая"}
        conf_label = conf_labels.get(confidence, confidence)
        st.metric("уверенность", f"{conf_emoji} {conf_label}")

    with warn_col:
        warnings = data.get("warnings", [])
        if warnings:
            st.warning("⚠️ предупреждения:\n" + "\n".join([f"- {w}" for w in warnings]))

    st.write("")

    # merchant and metadata
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        merchant = data.get("merchant")
        if merchant:
            st.info(f"**продавец:** {merchant}")
    with info_col2:
        date = data.get("date")
        if date:
            st.info(f"**дата:** {date}")

    st.write("")

    # items table
    items = data.get("items", [])
    if items:
        st.markdown("**позиции:**")

        # prepare table data
        table_data = []
        for item in items:
            table_data.append(
                {
                    "название": item.get("name", "—"),
                    "кол-во": item.get("quantity") if item.get("quantity") is not None else "—",
                    "цена": f"{item.get('price'):.2f}" if item.get("price") is not None else "—",
                    "сумма": f"{item.get('total'):.2f}" if item.get("total") is not None else "—",
                }
            )

        st.dataframe(table_data, use_container_width=True, hide_index=True)

    st.write("")

    # totals
    total_col1, total_col2, total_col3 = st.columns(3)

    with total_col1:
        subtotal = data.get("subtotal")
        if subtotal is not None:
            st.metric("подытог", f"{subtotal:.2f} ₽")

    with total_col2:
        tax = data.get("tax")
        if tax is not None:
            st.metric("ндс", f"{tax:.2f} ₽")

    with total_col3:
        total = data.get("total")
        if total is not None:
            st.metric("итого", f"{total:.2f} ₽")


def render_stage(stage: dict, storage: StorageClient):
    """render single pipeline stage"""

    info_col, badge_col, source_col = st.columns([6, 2, 1])

    with info_col:
        st.caption(stage.get("description", "No description"))

    with badge_col:
        # show alignment mode badge if available
        alignment_mode = _get_alignment_mode_badge(stage)
        if alignment_mode:
            if alignment_mode == "neural":
                st.markdown("🧠 `neural`")
            elif alignment_mode == "classic":
                st.markdown("📐 `classic`")
            else:
                st.markdown(f"`{alignment_mode}`")

    with source_col:
        source = stage.get("source", "gateway")
        st.caption(f"*{source}*")

    metadata = stage.get("metadata", {})
    if metadata:
        with st.expander("Details", expanded=False):
            # highlight important metadata
            important_keys = ["method", "fallback_used", "corners", "rect_angle"]
            other_metadata = {}

            for key in important_keys:
                if key in metadata:
                    value = metadata[key]
                    st.text(f"**{key}**: {value}")

            for key, value in metadata.items():
                if key not in important_keys and key != "description":
                    other_metadata[key] = value

            if other_metadata:
                st.write("")
                st.caption("**Other metadata:**")
                for key, value in other_metadata.items():
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
