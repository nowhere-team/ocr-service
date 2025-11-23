from io import BytesIO

import streamlit as st

from ..gateway_client import GatewayClient


def render_upload_form(gateway: GatewayClient) -> bool:
    """
    render image upload form

    args:
        gateway: gateway client

    returns:
        true if upload was successful
    """
    with st.form("upload_form", clear_on_submit=True, border=False):
        uploaded_file = st.file_uploader(
            "image",
            type=["jpg", "jpeg", "png", "webp"],
            help="supported: jpg, png, webp",
            label_visibility="collapsed",
        )

        if uploaded_file:
            st.image(
                uploaded_file,
                width=250,
                caption=f"{uploaded_file.name} • {uploaded_file.size / 1024:.1f} kb",
            )

        with st.expander("options", expanded=False):
            st.caption("**alignment algorithm**")
            alignment_col1, alignment_col2 = st.columns(2)

            with alignment_col1:
                use_classic = st.checkbox("classic (opencv)", value=False)
            with alignment_col2:
                use_neural = st.checkbox("neural (docaligner)", value=True)

            if use_classic and use_neural:
                st.warning("⚠️ both selected - neural will be used")
            elif not use_classic and not use_neural:
                st.warning("⚠️ no algorithm selected - neural is default")

            alignment_mode = "classic" if use_classic and not use_neural else "neural"

            st.caption("**source**")
            source_service = st.text_input(
                "source service", value="visualizer", help="service identifier"
            )

            source_reference = st.text_input(
                "source reference", value="manual-upload", help="reference identifier"
            )

            st.caption("**qr formats**")
            qr_col1, qr_col2, qr_col3 = st.columns(3)

            with qr_col1:
                accept_fiscal = st.checkbox("fiscal", value=True)
            with qr_col2:
                accept_url = st.checkbox("url", value=True)
            with qr_col3:
                accept_unknown = st.checkbox("unknown", value=False)

        st.write("")
        submitted = st.form_submit_button(
            "upload & process",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not uploaded_file:
                st.error("please select an image")
                return False

            accepted_qr_formats = []
            if accept_fiscal:
                accepted_qr_formats.append("fiscal")
            if accept_url:
                accepted_qr_formats.append("url")
            if accept_unknown:
                accepted_qr_formats.append("unknown")

            with st.spinner("uploading..."):
                uploaded_file.seek(0)

                result = gateway.upload_image(
                    image_file=BytesIO(uploaded_file.read()),
                    filename=uploaded_file.name,
                    source_service=source_service,
                    source_reference=source_reference,
                    accepted_qr_formats=accepted_qr_formats,
                    alignment_mode=alignment_mode,
                )

            if result:
                st.success(f"✅ created ({alignment_mode} mode)")
                st.caption(f"`{result['recognitionId'][:16]}...`")

                st.session_state.selected_job_id = result["recognitionId"]
                st.session_state.just_uploaded = True

                return True
            else:
                st.error("failed to upload")
                return False

    return False
