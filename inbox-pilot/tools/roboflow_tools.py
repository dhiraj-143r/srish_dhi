"""
InboxPilot — Roboflow Tool Wrapper
Computer vision via Roboflow REST API (no SDK needed — Python 3.14 compatible).
"""
import logging
import httpx
import base64
import tempfile
import os
from config import config

logger = logging.getLogger("inbox-pilot.tools.roboflow")


async def classify_attachment(attachment_url: str = None, image_bytes: bytes = None) -> dict:
    """Classify an email attachment using Roboflow REST API."""
    try:
        if attachment_url and not image_bytes:
            async with httpx.AsyncClient() as client:
                response = await client.get(attachment_url, timeout=30)
                image_bytes = response.content

        if not image_bytes:
            return {"status": "failed", "error": "No image data provided"}

        # Encode as base64
        img_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Use Roboflow hosted API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://detect.roboflow.com/clip/1",
                params={"api_key": config.ROBOFLOW_API_KEY},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=img_b64,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "model": "clip/1",
                    "predictions": result,
                }
            else:
                logger.warning(f"Roboflow API returned {response.status_code}")
                return {
                    "status": "partial",
                    "file_size_bytes": len(image_bytes),
                    "note": f"API returned status {response.status_code}",
                }

    except Exception as e:
        logger.error(f"Failed to classify attachment: {e}")
        return {"status": "failed", "error": str(e), "file_size_bytes": len(image_bytes) if image_bytes else 0}


def get_attachment_type(filename: str) -> str:
    """Determine attachment type from filename extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    type_map = {
        "jpg": "image", "jpeg": "image", "png": "image", "gif": "image", "webp": "image",
        "pdf": "document", "doc": "document", "docx": "document",
        "xls": "spreadsheet", "xlsx": "spreadsheet", "csv": "spreadsheet",
        "txt": "text", "md": "text",
        "zip": "archive", "rar": "archive",
    }
    return type_map.get(ext, "unknown")
