from io import BytesIO
from typing import Any

import requests


class GatewayClient:
    """http client for ocr gateway api"""

    def __init__(self, gateway_url: str):
        self.gateway_url = gateway_url.rstrip("/")
        self.session = requests.Session()

    def upload_image(
        self,
        image_file: BytesIO,
        filename: str,
        source_service: str | None = None,
        source_reference: str | None = None,
        accepted_qr_formats: list[str] | None = None,
        alignment_mode: str | None = None,
    ) -> dict[str, Any] | None:
        """
        upload image for recognition

        args:
            image_file: image file as bytes
            filename: original filename
            source_service: optional source service name
            source_reference: optional source reference
            accepted_qr_formats: optional list of accepted qr formats
            alignment_mode: optional alignment mode (classic or neural)

        returns:
            response dict with imageId and recognitionId or none if failed
        """
        try:
            files = {"image": (filename, image_file, "image/jpeg")}
            data = {}

            if source_service:
                data["sourceService"] = source_service
            if source_reference:
                data["sourceReference"] = source_reference
            if accepted_qr_formats is not None:
                data["acceptedQrFormats"] = ",".join(accepted_qr_formats)
            if alignment_mode:
                data["alignmentMode"] = alignment_mode

            response = self.session.post(
                f"{self.gateway_url}/api/v1/recognize",
                files=files,
                data=data,
                timeout=30,
            )

            if response.status_code == 202:
                return response.json()
            else:
                return None

        except Exception:
            return None

    def get_recognition_status(self, recognition_id: str) -> dict[str, Any] | None:
        """
        get recognition status

        args:
            recognition_id: recognition id

        returns:
            status dict or none if failed
        """
        try:
            response = self.session.get(
                f"{self.gateway_url}/api/v1/recognitions/{recognition_id}",
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception:
            return None
