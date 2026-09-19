import json
import re
import time
import anthropic

from src.config import settings
from src.schemas import AIDecision
from src.retrieval import retrieve

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

MODEL_NAME = "claude-opus-5"

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
3. If the ticket clearly matches a policy rule, apply it precisely using the exact day thresholds in the policy.
4. For shipping delays: 6-7 days = WAIT_AND_TRACK, 8-10 days = OPEN_SHIPPING_INVESTIGATION, more than 10 days = OFFER_REPLACEMENT_OR_REFUND. Apply these thresholds exactly.
5. Never return an action that is not in the valid actions list above.
6. The confidence value must reflect how certain you are given the available information.
7. Only return NEEDS_MORE_INFORMATION if genuinely critical information is missing. Do not return it when the policy thresholds can be applied directly from the information given.
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


def get_decision(message: str, retries: int = 2) -> AIDecision:
    context_chunks = retrieve(message, top_k=3)
    user_prompt = _build_user_prompt(message, context_chunks)

    last_error = None
    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model=MODEL_NAME,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_text = next(
                block.text for block in response.content if block.type == "text"
            )
            data = _extract_json(raw_text)
            decision = _validate_decision(data)
            return decision
        except anthropic.RateLimitError as e:
            last_error = str(e)
            if attempt < retries:
                time.sleep(15)
                continue
            return AIDecision(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.0,
                reason="The AI service is temporarily unavailable due to rate limiting. Please try again in a moment.",
                sources=[c["source"] for c in context_chunks],
            )
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            last_error = str(e)
            return AIDecision(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.0,
                reason="The AI service returned an error. Please try again.",
                sources=[c["source"] for c in context_chunks],
            )
        except (json.JSONDecodeError, KeyError, ValueError, StopIteration) as e:
            last_error = str(e)
            if attempt < retries:
                time.sleep(2)
                continue
            return AIDecision(
                action="NEEDS_MORE_INFORMATION",
                confidence=0.0,
                reason="The AI response could not be parsed. Please try again or provide more details.",
                sources=[c["source"] for c in context_chunks],
            )
