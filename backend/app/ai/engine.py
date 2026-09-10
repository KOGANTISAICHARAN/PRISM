"""PRISM AI engine.

Provider-agnostic wrapper around (a) multimodal image analysis and (b) the guided
complaint-intake assistant. Two providers are supported:

* ``openai``  - any OpenAI-compatible multimodal endpoint (key stays server-side)
* ``demo``    - deterministic, clearly-labelled demo responses so the full product
                flow works without external credentials (DEMO_MODE)

Safety rules enforced here (see docs/AI_PIPELINE.md):
- Only *visible* characteristics are described; nothing is confirmed.
- No accusation of a vendor, no medical diagnosis, no legal conclusion.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import settings

DISCLAIMER = (
    "AI-generated assessment. AI visual analysis is indicative only and does not confirm "
    "contamination or establish legal responsibility. Further inspection may be required."
)

ISSUE_TYPES = [
    "foreign_object",
    "mold_like_growth",
    "pest_evidence",
    "spoilage_discoloration",
    "packaging_damage",
    "leakage",
    "hygiene_concern",
    "other_visible_condition",
]

ISSUE_LABELS = {
    "foreign_object": "Possible foreign object",
    "mold_like_growth": "Possible mold-like growth",
    "pest_evidence": "Possible pest evidence",
    "spoilage_discoloration": "Possible spoilage / discoloration",
    "packaging_damage": "Possible packaging damage",
    "leakage": "Possible leakage",
    "hygiene_concern": "Possible hygiene concern",
    "other_visible_condition": "Other unusual visible condition",
}

SEVERITY = {
    "foreign_object": 4,
    "pest_evidence": 4,
    "mold_like_growth": 3,
    "spoilage_discoloration": 3,
    "hygiene_concern": 2,
    "leakage": 2,
    "packaging_damage": 2,
    "other_visible_condition": 1,
}

_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("foreign_object", ("plastic", "metal", "glass", "stone", "hair", "wire", "nail", "foreign", "object", "insect in", "worm")),
    ("pest_evidence", ("cockroach", "roach", "rat", "rodent", "pest", "fly", "flies", "larvae", "maggot", "insect")),
    ("mold_like_growth", ("mold", "mould", "fungus", "fungal", "green patch", "white patch", "furry")),
    ("spoilage_discoloration", ("spoil", "rotten", "smell", "smelt", "stale", "sour", "foul", "discolor", "discolour", "slimy", "expired", "bad taste", "tasted off")),
    ("packaging_damage", ("packaging", "package", "seal", "torn", "damaged pack", "bloated", "swollen pack")),
    ("leakage", ("leak", "leaking", "spilled", "oil seep")),
    ("hygiene_concern", ("dirty", "unhygienic", "hygiene", "unclean", "filthy", "wash")),
]

ILLNESS_WORDS = ("vomit", "diarrhea", "diarrhoea", "fever", "hospital", "food poisoning", "stomach", "nausea", "ill", "sick")

MEDICAL_NOTE = (
    "If you or anyone else is feeling unwell, please seek medical advice from a qualified "
    "professional. PRISM cannot assess health symptoms."
)

REQUIRED_FIELDS = [
    "vendor_name",
    "location",
    "food_item",
    "issue_type",
    "incident_datetime",
    "evidence_available",
    "user_description",
]

_QUESTIONS = {
    "user_description": "Please describe what happened in your own words.",
    "issue_type": "What did you notice in or about the food? (for example: a foreign object, mold-like growth, pest evidence, spoilage or damaged packaging)",
    "food_item": "Which food or product was it?",
    "vendor_name": "Which restaurant, shop or brand was it from?",
    "location": "Where was it purchased? (area or address)",
    "incident_datetime": "When did you buy or consume it? (date and approximate time)",
    "evidence_available": "Do you have any evidence you can share - photo, bill, both, or none?",
}


@dataclass
class VisionResult:
    detected_issue: str
    risk_level: str
    confidence: float
    explanation: str
    model: str = "demo"
    issue_type: str = "other_visible_condition"
    disclaimer: str = DISCLAIMER

    def as_dict(self) -> dict[str, Any]:
        return {
            "detected_issue": self.detected_issue,
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 2),
            "explanation": self.explanation,
            "issue_type": self.issue_type,
            "model": self.model,
            "disclaimer": self.disclaimer,
        }


@dataclass
class AssistantResult:
    fields: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    next_question: str | None = None
    complete: bool = False
    notice: str | None = None
    model: str = "demo"

    def as_dict(self) -> dict[str, Any]:
        return {
            "fields": self.fields,
            "missing_fields": self.missing_fields,
            "next_question": self.next_question,
            "complete": self.complete,
            "notice": self.notice,
            "model": self.model,
            "disclaimer": DISCLAIMER,
        }


# --------------------------------------------------------------------- helpers
def classify_text(text: str) -> tuple[str, float]:
    """Keyword issue classification. Returns (issue_type, confidence)."""
    low = (text or "").lower()
    best, hits = "other_visible_condition", 0
    for issue, words in _KEYWORDS:
        count = sum(1 for w in words if w in low)
        if count > hits:
            best, hits = issue, count
    confidence = min(0.55 + 0.12 * hits, 0.93) if hits else 0.4
    return best, confidence


def risk_level_for(issue_type: str) -> str:
    sev = SEVERITY.get(issue_type, 1)
    return "High" if sev >= 4 else "Moderate" if sev >= 2 else "Low"


def _extract_datetime(text: str) -> str | None:
    low = (text or "").lower()
    now = datetime.now(timezone.utc)
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2}([ T]\d{1,2}:\d{2})?)\b", text or "")
    if iso:
        return iso.group(1)
    time_m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low)
    if "today" in low or "tonight" in low or "yesterday" in low or time_m:
        day = now.date()
        if "yesterday" in low:
            day = day.fromordinal(day.toordinal() - 1)
        hour, minute = 20, 0
        if time_m:
            hour = int(time_m.group(1)) % 12
            minute = int(time_m.group(2) or 0)
            if time_m.group(3) == "pm":
                hour += 12
        return f"{day.isoformat()} {hour:02d}:{minute:02d}"
    return None


def _extract_vendor(text: str) -> str | None:
    if not text:
        return None
    m = re.search(
        r"(?:from|at|in)\s+((?:[A-Z][\w&'.-]*\s?){1,4}(?:Restaurant|Hotel|Cafe|Café|Biryani|Bites|Corner|Kitchen|Dhaba|Bakery|Store|Mart)?)",
        text,
    )
    if m:
        candidate = m.group(1).strip(" .,")
        if len(candidate) > 2 and not candidate.lower() in {"the", "my", "a"}:
            return candidate
    return None


FOOD_WORDS = (
    "biryani", "biriyani", "curry", "rice", "chicken", "mutton", "paneer", "milk", "juice", "roti",
    "naan", "pizza", "burger", "noodles", "samosa", "dosa", "idli", "salad", "fish", "egg", "cake",
    "bread", "sandwich", "shawarma", "momos", "ice cream", "yogurt", "curd", "water bottle",
)


def _extract_food(text: str) -> str | None:
    low = (text or "").lower()
    filler = {"my", "the", "a", "an", "some", "this", "that", "in", "of", "from", "found", "had"}
    for w in FOOD_WORDS:
        if w in low:
            m = re.search(rf"((?:\w+\s){{0,2}}{re.escape(w)})", low)
            words = (m.group(1) if m else w).split()
            while words and words[0] in filler:
                words.pop(0)
            return " ".join(words).strip().title()
    return None


def _extract_evidence(text: str) -> str | None:
    low = (text or "").lower()
    has_photo = any(w in low for w in ("photo", "picture", "image", "pic"))
    has_bill = any(w in low for w in ("bill", "receipt", "invoice"))
    if has_photo and has_bill:
        return "both"
    if has_photo:
        return "photo"
    if has_bill:
        return "bill"
    if "no evidence" in low or low.strip() in {"none", "no"}:
        return "none"
    return None


def _extract_location(text: str) -> str | None:
    m = re.search(r"(?:in|near|at)\s+([A-Z][\w.'-]+(?:\s[A-Z][\w.'-]+){0,3})", text or "")
    return m.group(1).strip(" .,") if m else None


# --------------------------------------------------------------------- provider
class AIEngine:
    def __init__(self) -> None:
        self.provider = settings.ai_provider if settings.ai_api_key else "demo"

    @property
    def mode(self) -> str:
        return self.provider

    # ---------------------------------------------------------------- vision
    def analyze_image(self, data: bytes, content_type: str, hint: str = "") -> VisionResult:
        if self.provider == "openai":
            try:
                return self._openai_vision(data, content_type, hint)
            except Exception as exc:  # graceful fallback keeps the flow alive
                result = self._demo_vision(data, hint)
                result.explanation += f" (Live AI provider unavailable, demo analysis used: {type(exc).__name__})"
                return result
        return self._demo_vision(data, hint)

    def _demo_vision(self, data: bytes, hint: str) -> VisionResult:
        issue_type, confidence = classify_text(hint)
        if issue_type == "other_visible_condition":
            # deterministic pseudo-analysis keyed on file bytes so demos are repeatable
            idx = int(hashlib.sha256(data).hexdigest(), 16) % 4
            issue_type = ["foreign_object", "spoilage_discoloration", "mold_like_growth", "packaging_damage"][idx]
            confidence = 0.72 + (idx * 0.05)
        label = ISSUE_LABELS[issue_type]
        return VisionResult(
            detected_issue=label,
            risk_level=risk_level_for(issue_type),
            confidence=confidence,
            explanation=(
                f"{label.lower().capitalize()}-like characteristics appear visible in the submitted image. "
                "This is a visual signal only and further inspection may be required."
            ),
            model="prism-demo-vision",
            issue_type=issue_type,
        )

    def _openai_vision(self, data: bytes, content_type: str, hint: str) -> VisionResult:
        b64 = base64.b64encode(data).decode()
        system = (
            "You are a food-safety image analyst for a decision-support platform. Describe ONLY visible "
            "characteristics. Never confirm contamination, never accuse a business, never diagnose illness. "
            f"Choose detected_issue from: {', '.join(ISSUE_TYPES)}. "
            'Reply with strict JSON: {"issue_type": str, "detected_issue": str, "risk_level": "Low|Moderate|High", '
            '"confidence": float, "explanation": str}. Use hedged language such as "possible" or "appears".'
        )
        payload = {
            "model": settings.ai_vision_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Citizen note: {hint or '(none)'}"},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{b64}"}},
                    ],
                },
            ],
        }
        raw = self._chat(payload)
        issue_type = raw.get("issue_type") if raw.get("issue_type") in ISSUE_TYPES else "other_visible_condition"
        return VisionResult(
            detected_issue=raw.get("detected_issue") or ISSUE_LABELS[issue_type],
            risk_level=raw.get("risk_level") if raw.get("risk_level") in ("Low", "Moderate", "High") else risk_level_for(issue_type),
            confidence=float(raw.get("confidence") or 0.6),
            explanation=raw.get("explanation") or "",
            model=settings.ai_vision_model,
            issue_type=issue_type,
        )

    # ------------------------------------------------------------- assistant
    def structure_complaint(
        self,
        messages: list[dict[str, str]],
        known: dict[str, Any] | None = None,
        vision: dict[str, Any] | None = None,
    ) -> AssistantResult:
        known = {k: v for k, v in (known or {}).items() if v not in (None, "", [])}
        if self.provider == "openai":
            try:
                return self._openai_assistant(messages, known, vision)
            except Exception:
                pass
        return self._demo_assistant(messages, known, vision)

    def _slots_from_conversation(
        self, messages: list[dict[str, str]], known: dict[str, Any], vision: dict[str, Any] | None
    ) -> dict[str, Any]:
        fields = dict(known)
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user").strip()

        if vision and not fields.get("issue_type"):
            fields["issue_type"] = vision.get("issue_type") or "other_visible_condition"
        if user_text:
            fields.setdefault("user_description", user_text)
            if not fields.get("issue_type"):
                issue_type, _ = classify_text(user_text)
                if issue_type != "other_visible_condition":
                    fields["issue_type"] = issue_type
            for key, extractor in (
                ("vendor_name", _extract_vendor),
                ("food_item", _extract_food),
                ("incident_datetime", _extract_datetime),
                ("evidence_available", _extract_evidence),
                ("location", _extract_location),
            ):
                if not fields.get(key):
                    value = extractor(user_text)
                    if value:
                        fields[key] = value
        # The most recent answer responds to the last question asked.
        last_q = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "assistant"), "")
        last_a = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        if last_q and last_a:
            for slot, question in _QUESTIONS.items():
                if question[:28].lower() in last_q.lower() and not fields.get(slot):
                    fields[slot] = last_a.strip()
        return fields

    def _demo_assistant(
        self, messages: list[dict[str, str]], known: dict[str, Any], vision: dict[str, Any] | None
    ) -> AssistantResult:
        fields = self._slots_from_conversation(messages, known, vision)
        missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
        user_text = " ".join(m.get("content", "") for m in messages if m.get("role") == "user").lower()
        notice = MEDICAL_NOTE if any(w in user_text for w in ILLNESS_WORDS) else None
        question = _QUESTIONS.get(missing[0]) if missing else None
        return AssistantResult(
            fields=fields,
            missing_fields=missing,
            next_question=question,
            complete=not missing,
            notice=notice,
            model="prism-demo-assistant",
        )

    def _openai_assistant(
        self, messages: list[dict[str, str]], known: dict[str, Any], vision: dict[str, Any] | None
    ) -> AssistantResult:
        system = (
            "You are PRISM's guided food-safety complaint intake assistant (slot filling, NOT a general chatbot).\n"
            f"Required fields: {', '.join(REQUIRED_FIELDS)}.\n"
            "Rules: never re-ask a field that is already known or derivable from the conversation; ask at most "
            "1-2 short, simple questions per turn; never accuse a vendor; never diagnose illness (if symptoms are "
            "mentioned, set notice advising medical advice); use hedged language (possible/suspected/reported).\n"
            f"issue_type must be one of: {', '.join(ISSUE_TYPES)}.\n"
            'Reply with strict JSON: {"fields": {...}, "missing_fields": [...], "next_question": str|null, '
            '"complete": bool, "notice": str|null}.'
        )
        context = {"known_fields": known, "image_analysis": vision or None}
        payload = {
            "model": settings.ai_text_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "system", "content": f"Context: {json.dumps(context, default=str)}"},
                *[{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages],
            ],
        }
        raw = self._chat(payload)
        fields = {k: v for k, v in (raw.get("fields") or {}).items() if k in REQUIRED_FIELDS and v}
        fields = {**self._slots_from_conversation(messages, known, vision), **fields}
        missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]
        return AssistantResult(
            fields=fields,
            missing_fields=missing,
            next_question=(raw.get("next_question") or (_QUESTIONS.get(missing[0]) if missing else None)),
            complete=not missing,
            notice=raw.get("notice"),
            model=settings.ai_text_model,
        )

    # ------------------------------------------------------------------ http
    def _chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.post(
            f"{settings.ai_base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            timeout=90,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return json.loads(content)


ai_engine = AIEngine()
