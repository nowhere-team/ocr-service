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
            "Image",
            type=["jpg", "jpeg", "png", "webp"],
            help="Supported: jpg, png, webp",
            label_visibility="collapsed",
        )

        if uploaded_file:
            st.image(
                uploaded_file,
                width=250,
                caption=f"{uploaded_file.name} • {uploaded_file.size / 1024:.1f} KB",
            )

        with st.expander("Options", expanded=False):
            source_service = st.text_input(
                "Source Service", value="visualizer", help="Service identifier"
            )

            source_reference = st.text_input(
                "Source Reference", value="manual-upload", help="Reference identifier"
            )

            st.caption("**QR Formats**")
            qr_col1, qr_col2, qr_col3 = st.columns(3)

            with qr_col1:
                accept_fiscal = st.checkbox("Fiscal", value=True)
            with qr_col2:
                accept_url = st.checkbox("URL", value=True)
            with qr_col3:
                accept_unknown = st.checkbox("Unknown", value=False)

        st.write("")
        submitted = st.form_submit_button(
            "Upload & Process",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not uploaded_file:
                st.error("Please select an image")
                return False

            accepted_qr_formats = []
            if accept_fiscal:
                accepted_qr_formats.append("fiscal")
            if accept_url:
                accepted_qr_formats.append("url")
            if accept_unknown:
                accepted_qr_formats.append("unknown")

            with st.spinner("Uploading..."):
                uploaded_file.seek(0)

                result = gateway.upload_image(
                    image_file=BytesIO(uploaded_file.read()),
                    filename=uploaded_file.name,
                    source_service=source_service,
                    source_reference=source_reference,
                    accepted_qr_formats=accepted_qr_formats if accepted_qr_formats else None,
                )

            if result:
                st.success("✅ Created")
                st.caption(f"`{result['recognitionId'][:16]}...`")

                st.session_state.selected_job_id = result["recognitionId"]
                st.session_state.just_uploaded = True

                return True
            else:
                st.error("Failed to upload")
                return False

    return False
