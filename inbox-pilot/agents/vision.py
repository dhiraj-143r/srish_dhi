"""
InboxPilot — Vision Agent
Uses Roboflow to analyze email attachments (images, documents).
Classifies attachment types and extracts visual information.
"""
import logging
import time
import httpx
from agents.state import EmailState
from tools.roboflow_tools import classify_attachment, get_attachment_type

logger = logging.getLogger("inbox-pilot.agents.vision")


async def vision_agent(state: EmailState) -> dict:
    """
    Analyze email attachments using Roboflow computer vision.
    Classifies images and documents attached to the email.
    """
    log = state.get("processing_log", [])
    attachments = state.get("attachments", [])

    if not attachments:
        log.append({"agent": "vision", "status": "skipped", "ts": time.time(), "msg": "👁️ No attachments to analyze"})
        return {
            "attachment_analysis": [],
            "attachment_summary": "No attachments found.",
            "processing_log": log,
        }

    log.append({
        "agent": "vision",
        "status": "started",
        "ts": time.time(),
        "msg": f"👁️ Analyzing {len(attachments)} attachment(s) with Roboflow..."
    })

    analysis_results = []
    for i, attachment in enumerate(attachments):
        # Handle different attachment formats from AgentMail
        if isinstance(attachment, dict):
            filename = attachment.get("filename", attachment.get("name", f"attachment_{i}"))
            url = attachment.get("url", attachment.get("content_url", ""))
            content_type = attachment.get("content_type", attachment.get("type", ""))
        elif isinstance(attachment, str):
            filename = f"attachment_{i}"
            url = attachment
            content_type = ""
        else:
            filename = getattr(attachment, 'filename', f"attachment_{i}")
            url = getattr(attachment, 'url', getattr(attachment, 'content_url', ''))
            content_type = getattr(attachment, 'content_type', '')

        file_type = get_attachment_type(filename)

        attachment_result = {
            "filename": filename,
            "file_type": file_type,
            "content_type": content_type,
        }

        # Only analyze image attachments with Roboflow
        if file_type == "image" and url:
            try:
                classification = await classify_attachment(attachment_url=url)
                attachment_result["classification"] = classification
                attachment_result["analyzed"] = True
            except Exception as e:
                logger.warning(f"Failed to classify {filename}: {e}")
                attachment_result["classification"] = {"status": "failed", "error": str(e)}
                attachment_result["analyzed"] = False
        else:
            attachment_result["analyzed"] = False
            attachment_result["note"] = f"File type '{file_type}' — visual analysis not applicable"

        analysis_results.append(attachment_result)

    # Build summary
    analyzed_count = sum(1 for r in analysis_results if r.get("analyzed"))
    type_counts = {}
    for r in analysis_results:
        ft = r.get("file_type", "unknown")
        type_counts[ft] = type_counts.get(ft, 0) + 1

    type_summary = ", ".join(f"{count} {ftype}(s)" for ftype, count in type_counts.items())
    summary = f"Found {len(attachments)} attachment(s): {type_summary}. Analyzed {analyzed_count} with Roboflow."

    log.append({
        "agent": "vision",
        "status": "completed",
        "ts": time.time(),
        "msg": f"✅ Vision complete: {summary}"
    })

    return {
        "attachment_analysis": analysis_results,
        "attachment_summary": summary,
        "processing_log": log,
    }
