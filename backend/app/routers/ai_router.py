from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..ai.engine import DISCLAIMER, ISSUE_LABELS, REQUIRED_FIELDS, SEVERITY, ai_engine
from ..auth import optional_user
from ..config import settings
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status")
def ai_status():
    return {
        "provider": ai_engine.mode,
        "demo_mode": settings.demo_mode,
        "vision_model": settings.ai_vision_model if ai_engine.mode == "openai" else "prism-demo-vision",
        "issue_labels": ISSUE_LABELS,
        "severity": SEVERITY,
        "required_fields": REQUIRED_FIELDS,
        "disclaimer": DISCLAIMER,
    }


@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    hint: str = Form(""),
    user: User | None = Depends(optional_user),
):
    """Analyse visible characteristics of an uploaded image. Indicative only."""
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only image files can be analysed")
    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Image exceeds {settings.max_upload_mb} MB")
    result = ai_engine.analyze_image(data, content_type, hint)
    return result.as_dict()


class AssistantIn(BaseModel):
    messages: list[dict[str, str]] = []
    known_fields: dict[str, Any] = {}
    vision: dict[str, Any] | None = None


@router.post("/structure-complaint")
def structure_complaint(payload: AssistantIn, db: Session = Depends(get_db)):
    """Guided slot-filling intake: returns structured fields + only the missing question."""
    result = ai_engine.structure_complaint(payload.messages, payload.known_fields, payload.vision)
    return result.as_dict()
