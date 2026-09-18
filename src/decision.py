import json
import re
import google.generativeai as genai

from src.config import settings
from src.schemas import AIDecision
from src.retrieval import retrieve

genai.configure(api_key=settings.gemini_api_key)

VALID_ACTIONS = [
    "APPROVE_REFUND_OR_REPLACEMENT",
    "APPROVE_REPLACEMENT",
    "APPROVE_RETURN",
    "CANCEL_AND_REFUND",
    "CANNOT_CANCEL_AFTER_DISPATCH",
    "NEEDS_MORE_INFORMATION",
    "OFFER_REPLACEMENT_OR_REFUND",
    "OPEN_SHIPPING_INVESTIGATION",
    "REJECT_FOOD_RETURN",
    "REJECT_OPENED_ITEM",
    "REJECT_OUTSIDE_WINDOW",
    "REPLACE_CORRECT_ITEM",
    "REQUEST_DEFECT_EVIDENCE",
    "REQUEST_PHOTOS",
    "WAIT_AND_TRACK",
]

SYSTEM_PROMPT = """You are a customer support decision assistant for an e-commerce company.

Your job is to read a customer support ticket and the relevant company policy excerpts, then decide what action to take.

You must respond with ONLY a valid JSON object. No explanation before or after. No markdown fences. Just the raw JSON.

The JSON must have exactly these four fields:
- action: one of the valid actions listed below (string)
- confidence: a number between 0.0 and 1.0 (float)
- reason: a clear one or two sentence explanation of why you chose this action (string)
- sources: a list of the policy filenames you used to make the decision (list of strings)

Valid actions (choose exactly one):
APPROVE_REFUND_OR_REPLACEMENT
APPROVE_REPLACEMENT
APPROVE_RETURN
CANCEL_AND_REFUND
CANNOT_CANCEL_AFTER_DISPATCH
NEEDS_MORE_INFORMATION
OFFER_REPLACEMENT_OR_REFUND
OPEN_SHIPPING_INVESTIGATION
REJECT_FOOD_RETURN
REJECT_OPENED_ITEM
REJECT_OUTSIDE_WINDOW
REPLACE_CORRECT_ITEM
REQUEST_DEFECT_EVIDENCE
REQUEST_PHOTOS
WAIT_AND_TRACK

Rules you must follow:
1. Only use the policy excerpts provided. Do not invent policies.
2. If the ticket is missing information needed to make a decision, return NEEDS_MORE_INFORMATION.
3. If the ticket clearly matches a policy rule, apply it precisely.
4. Never return an action that is not in the valid actions list above.
5. The confidence value must reflect how certain you are given the available information.
"""


def _build_user_prompt(message: str, context_chunks: list[dict]) -> str:
    context_text = ""
    for chunk in context_chunks:
        context_text += f"\n--- {chunk['source']} ---\n{chunk['text']}\n"

    return f"""CUSTOMER TICKET:
{message}

RELEVANT POLICY EXCERPTS:
{context_text}

Respond with only the JSON decision object."""


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw, strict=False)


def _validate_decision(data: dict) -> AIDecision:
    if data.get("action") not in VALID_ACTIONS:
        data["action"] = "NEEDS_MORE_INFORMATION"
    decision = AIDecision(**data)
    return decision


def get_decision(message: str) -> AIDecision:
    context_chunks = retrieve(message, top_k=3)
    user_prompt = _build_user_prompt(message, context_chunks)

    model = genai.GenerativeModel(
        model_name="gemini-3.6-flash",
        system_instruction=SYSTEM_PROMPT,
    )

    try:
        response = model.generate_content(user_prompt)
        raw_text = response.text
        data = _extract_json(raw_text)
        decision = _validate_decision(data)
        return decision
    except (json.JSONDecodeError, KeyError, ValueError):
        return AIDecision(
            action="NEEDS_MORE_INFORMATION",
            confidence=0.0,
            reason="The AI response could not be parsed. Please try again or provide more details.",
            sources=[c["source"] for c in context_chunks],
        )
