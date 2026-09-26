"""Campus Customs shop agent: loads prompts/prompt.md, wires the model and tools, runs one chat turn.

Problem 12 adds three safety layers around the model and an append-only audit trail:
  * redact_sensitive()  - card numbers / passwords / SSNs are removed before the model, DB or audit log see them
  * check_reply()       - output validator: every $ price must come from a tool result this turn; no fake
                          checkouts, orders, holds, codes or links (the model is sent back to fix it)
  * output/audit_trail.json - every run's steps (time, tool, short args/result, stop reason), appended, never wiped
"""

import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from models import AuditEntry, ChatReply, ChatTurn, CurrentPage, CustomerProfile, ShopDeps, ShopReply
from tools import (
    catalogue_overview,
    check_stock,
    find_similar_products,
    get_product_info,
    page_results,
    product_cards,
    recall_past_chats,
    search_products,
)

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompts" / "prompt.md"
AUDIT_PATH = HERE.parent / "output" / "audit_trail.json"
MODEL_NAME = "gpt-5.6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MAX_HISTORY_TURNS = 12  # most recent messages replayed to the model
USAGE_LIMITS = UsageLimits(request_limit=6, tool_calls_limit=8)  # caps the agent loop per chat message
AUDIT_TEXT_LIMIT = 240

USAGE_LIMIT_REPLY = "Sorry, that one took me too long to work out. Could you ask it a simpler way?"
FILTERED_REPLY = (
    "I can't help with that one, but I'd love to help you find some Bulldog gear! "
    "Ask me about hoodies, crewnecks, tees, sizes or gift ideas."
)

log = logging.getLogger("campus_customs")

# HW4/.env first, then the course-level .env (where PORTKEY_API_KEY lives).
load_dotenv(HERE.parent / ".env")
load_dotenv(HERE.parent.parent / ".env")


class AgentUnavailable(Exception):
    """The model/provider failed for a reason other than limits or the content filter (-> HTTP 502)."""


# =========================================================================
# Safety layer 1: redact sensitive personal data before anyone sees it
# =========================================================================

_REDACTIONS = [
    # 13-19 digit card numbers, optionally grouped with spaces/dashes
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "[card number removed]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN removed]"),
    (re.compile(r"(?i)\b(cvv|cvc|security code)\s*(?:is|:|=)?\s*\d{3,4}\b"), r"\1 [removed]"),
    (re.compile(r"(?i)\b(password|passcode|passwd|pwd|pin)(\s*(?:is|:|=)\s*)\S+"), r"\1\2[removed]"),
]


def redact_sensitive(text: str) -> tuple[str, bool]:
    """Replace card numbers, SSNs, CVVs and passwords with placeholders. Returns (clean_text, changed)."""
    clean = text
    for pattern, repl in _REDACTIONS:
        clean = pattern.sub(repl, clean)
    return clean, clean != text


# =========================================================================
# Safety layer 2: output validator (runs on every final answer)
# =========================================================================

_PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_FAKE_COMMERCE = [
    re.compile(p, re.I)
    for p in [
        r"\byour order (?:has been|is|was) (?:placed|confirmed|processed|complete)",
        r"\b(?:added|put) (?:it|that|this|them|one)?\s*(?:in|into|to) your (?:cart|bag|basket)\b",
        r"\b(?:here(?:'s| is)|use|click) (?:a|your|the|this) (?:checkout|payment|purchase) link\b",
        r"\b(?:use|enter|apply) (?:the )?(?:code|coupon|promo(?: code)?|discount code)\s+[A-Z0-9]{3,}",
        r"\bi(?:'ve| have| just)? (?:reserved|held|set aside|placed an order|charged|processed)\b",
        r"\b(?:payment|purchase|checkout) (?:is |was |has been )?(?:complete|successful|processed|confirmed)\b",
    ]
]


def _grounded_numbers(ctx: RunContext[ShopDeps]) -> set[float]:
    """Numbers the reply may quote as prices: tool results this run, the shopper's own words, the current page."""
    texts: list[str] = []
    for msg in ctx.messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    texts.append(part.model_response_str())
                elif isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    texts.append(part.content)  # budgets the shopper named ("under $50")
    if ctx.deps.page and ctx.deps.page.product:
        texts.append(str(ctx.deps.page.product.price))
    return {float(n) for t in texts for n in _NUMBER_RE.findall(t.replace(",", ""))}


def check_reply(ctx: RunContext[ShopDeps], reply: ShopReply) -> ShopReply:
    """Reject replies that invent prices or pretend to sell. ModelRetry sends the model back to fix it."""
    text = reply.message
    allowed = _grounded_numbers(ctx)
    for amount in _PRICE_RE.findall(text):
        if float(amount.replace(",", "")) not in allowed:
            raise ModelRetry(
                f"You wrote ${amount}, but no tool result in this turn contains that price. Look it up with "
                "get_product_info / search_products and quote the exact price, or leave the price out."
            )
    for pattern in _FAKE_COMMERCE:
        if pattern.search(text):
            raise ModelRetry(
                "You can't place orders, take payment, hold items, add to a cart or give discount codes. "
                "Rewrite the reply without claiming any of that; point the shopper to the website or 57 Broadway instead."
            )
    if re.search(r"https?://|www\.", text, re.I):
        raise ModelRetry("Don't include links or URLs; the site shows product cards for you.")
    return reply


# =========================================================================
# Agent
# =========================================================================

@lru_cache(maxsize=1)
def build_agent() -> Agent[ShopDeps, ShopReply]:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set (expected in HW4/.env or the parent .env).")
    model = OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(api_key=api_key, base_url=PORTKEY_BASE_URL))
    agent = Agent(
        model,
        deps_type=ShopDeps,
        output_type=ShopReply,
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8"),
        tools=[
            search_products,
            get_product_info,
            check_stock,
            find_similar_products,
            catalogue_overview,
            recall_past_chats,
        ],
        model_settings=ModelSettings(timeout=60),
        retries=2,
    )

    # Re-evaluated on every run, so each message sees the current shopper and page.
    @agent.instructions
    def shopper_context(ctx: RunContext[ShopDeps]) -> str:
        return describe_customer(ctx.deps.customer)

    @agent.instructions
    def page_context(ctx: RunContext[ShopDeps]) -> str:
        return describe_page(ctx.deps.page)

    agent.output_validator(check_reply)
    return agent


def describe_customer(c: CustomerProfile | None) -> str:
    if c is None:
        return "## Who you're talking to\nA guest (not logged in). You don't know their name, and nothing is saved after they leave."
    return (
        "## Who you're talking to\n"
        f"A logged-in customer: **{c.first_name} {c.last_name}**, account email {c.email}, "
        f"member since {c.member_since}, {c.saved_messages} saved chat messages. "
        "Earlier messages from their past visits are included in this conversation; "
        "use `recall_past_chats` for anything older."
    )


def describe_page(p: CurrentPage | None) -> str:
    if p is None:
        return "## Current page\nUnknown."
    lines = [f"## Current page\nThe shopper is on `{p.path}` ({p.page} page) while chatting."]
    if p.product:
        pr = p.product
        lines.append(
            f"They are looking at **{pr.name}** (product_id `{pr.product_id}`, {pr.garment_type}, "
            f"colors: {', '.join(pr.colors)}, price {pr.price_display}). "
            '"This", "it", "this one" or "that" with no other item named means this product.'
        )
    if p.results_title:
        filters = f" (filters: {', '.join(p.results_filters)})" if p.results_filters else ""
        lines.append(f'The page is showing your earlier search results "{p.results_title}"{filters}; "these"/"those" can mean them.')
    if p.preferred_size:
        lines.append(
            f'The shopper has set their size to **{p.preferred_size}** on the site. "My size" means {p.preferred_size}; '
            "use it for stock checks and similar-item searches unless they name another size."
        )
    return "\n".join(lines)


def to_model_history(history: list[ChatTurn]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return messages


# =========================================================================
# Audit trail: output/audit_trail.json (append-only JSON array)
# =========================================================================

_audit_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _short(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    text, _ = redact_sensitive(" ".join(text.split()))
    return text if len(text) <= AUDIT_TEXT_LIMIT else text[: AUDIT_TEXT_LIMIT - 1] + "…"


def _summarize_result(content: object) -> str:
    """One short line per tool result, e.g. '3 results: a, b, c' or a StockReport's own summary."""
    if isinstance(content, list):
        items = [_summarize_result(c) for c in content[:6]]
        ids = [getattr(c, "product_id", None) for c in content]
        if all(ids) and not any(hasattr(c, "summary") for c in content):
            return _short(f"{len(content)} results: {', '.join(ids[:6])}")
        return _short(f"{len(content)} results: " + " | ".join(items))
    if isinstance(content, BaseModel):
        for attr in ("summary", "message", "note"):
            val = getattr(content, attr, None)
            if isinstance(val, str) and val:
                return _short(val)
        if hasattr(content, "price_display"):
            return _short(f"{content.name} {content.price_display}")
        if hasattr(content, "matches"):
            return _short(f"{len(content.matches)} matches: {', '.join(m.product_id for m in content.matches)}")
        return _short(content.model_dump(mode="json"))
    return _short(content)


def append_audit(entries: list[AuditEntry]) -> None:
    """Append entries to output/audit_trail.json. Never truncates: a file that can't be parsed is kept aside."""
    if not entries:
        return
    with _audit_lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if AUDIT_PATH.is_file() and AUDIT_PATH.stat().st_size:
            try:
                existing = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    raise ValueError("audit trail is not a JSON array")
            except ValueError:
                # Preserve the unreadable file instead of overwriting it, then start a fresh array.
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                AUDIT_PATH.rename(AUDIT_PATH.with_name(f"audit_trail.unreadable-{stamp}.json"))
                existing = []
        existing.extend(e.model_dump(mode="json", exclude_none=True) for e in entries)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, AUDIT_PATH)  # atomic: readers never see a half-written file


def _loop_entries(messages: list[ModelMessage], base: dict, first_new: int) -> list[AuditEntry]:
    """Turn this run's messages into per-step audit entries (tool calls, their results, retries)."""
    entries: list[AuditEntry] = []
    calls: dict[str, AuditEntry] = {}
    iteration = 0
    for msg in messages[first_new:]:
        if isinstance(msg, ModelResponse):
            iteration += 1
            for part in msg.parts:
                if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                    entry = AuditEntry(
                        **base,
                        time=msg.timestamp.isoformat(timespec="milliseconds"),
                        iteration=iteration,
                        event="tool_call",
                        tool_name=part.tool_name,
                        tool_args=_short(part.args_as_dict()),
                    )
                    calls[part.tool_call_id] = entry
                    entries.append(entry)
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart) and part.tool_call_id in calls:
                    calls[part.tool_call_id].result = _summarize_result(part.content)
                elif isinstance(part, RetryPromptPart):
                    is_output = part.tool_name in (None, "final_result")
                    entries.append(
                        AuditEntry(
                            **base,
                            time=part.timestamp.isoformat(timespec="milliseconds"),
                            iteration=iteration,
                            event="output_retry" if is_output else "tool_retry",
                            tool_name=None if is_output else part.tool_name,
                            result=_short(part.content if isinstance(part.content, str) else str(part.content)),
                        )
                    )
    return entries


# =========================================================================
# One chat turn
# =========================================================================

async def run_chat(message: str, history: list[ChatTurn], deps: ShopDeps) -> ChatReply:
    """Run the agent for one message and audit every step. `message` should already be redacted."""
    base = {
        "run_id": uuid.uuid4().hex[:12],
        "actor": f"user:{deps.customer.user_id}" if deps.customer else "guest",
        "page": deps.page.path if deps.page else None,
    }
    model_history = to_model_history(history)
    audit = [AuditEntry(**base, time=_now(), iteration=0, event="run_start", result=_short(f"message: {message}"))]
    stop_reason, usage, result = "model_error", None, None
    reply: ChatReply | None = None
    error: Exception | None = None

    with capture_run_messages() as messages:
        try:
            result = await build_agent().run(
                message, message_history=model_history, deps=deps, usage_limits=USAGE_LIMITS
            )
            out: ShopReply = result.output
            # Cards and page results are rebuilt from the database, so only real products (with live stock) are shown.
            reply = ChatReply(
                content=out.message,
                products=product_cards(out.product_ids),
                page_results=page_results(out.page_search) if out.page_search else None,
                suggestions=[s.strip()[:60] for s in out.suggestions if s.strip()][:3],
            )
            stop_reason = "final_result"
        except UsageLimitExceeded:
            stop_reason, reply = "usage_limit", ChatReply(content=USAGE_LIMIT_REPLY)
        except ModelHTTPError as exc:
            # The provider's content filter blocks jailbreak/harmful prompts; answer in voice instead of erroring.
            if "content_filter" in str(exc.body):
                stop_reason, reply = "content_filter", ChatReply(content=FILTERED_REPLY)
            else:
                error = exc
        except Exception as exc:  # log the type only, never message content or keys
            error = exc

    audit += _loop_entries(list(messages), base, first_new=len(model_history))
    if result is not None:
        u = result.usage() if callable(result.usage) else result.usage  # property in pydantic-ai 2.x
        usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}
    final_summary = (
        _short(f"reply: {reply.content} | cards: {[c.product_id for c in reply.products]}"
               + (f" | page: {reply.page_results.title} ({len(reply.page_results.products)})" if reply.page_results else ""))
        if reply
        else _short(f"error: {type(error).__name__}")
    )
    audit.append(
        AuditEntry(**base, time=_now(), iteration=max((e.iteration for e in audit), default=0), event="final",
                   stop_reason=stop_reason, result=final_summary, usage=usage)
    )
    try:
        append_audit(audit)
    except OSError as exc:  # auditing must never break the shop
        log.error("audit trail write failed: %s", type(exc).__name__)

    if reply is None:
        log.error("chat agent failed: %s", type(error).__name__)
        raise AgentUnavailable() from error
    return reply


if __name__ == "__main__":
    # Quick terminal check:  python agent.py "do you have gray hoodies in M?"
    import asyncio
    import sys

    question, _ = redact_sensitive(" ".join(sys.argv[1:]) or "What hoodies do you have?")
    out = asyncio.run(run_chat(question, [], ShopDeps()))
    print(out.content)
    for card in out.products:
        print(f"  - {card.name} (${card.price:.0f}) sizes: {', '.join(card.sizes_in_stock)}")
