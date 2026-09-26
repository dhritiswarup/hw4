"""Pydantic / PydanticAI structured types for the Campus Customs backend and agent."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

# ---------- catalogue (API responses + tool results) ----------


class SizeStock(BaseModel):
    size: str
    quantity: int


class Product(BaseModel):
    """A catalogue row with JSON columns parsed and stock summed. Returned by GET /api/products."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    image_url: str
    price: float
    total_stock: int
    sizes_in_stock: list[str] = Field(default_factory=list, description="Sizes with quantity > 0 (Problem 9 size filter).")
    size_stock: dict[str, int] = Field(default_factory=dict, description="Quantity per size, for low-stock hints.")


class ProductDetail(Product):
    """Product plus per-size stock (XS→XXL). Returned by GET /api/products/{id} and the details tool."""

    inventory: list[SizeStock]


class ProductSummary(BaseModel):
    """Compact search hit given to the agent: enough to recommend, small enough to keep tokens low."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    sizes_in_stock: list[str]
    total_stock: int
    short_description: str


# ---------- product info + stock lookups (agent tool results, Problem 6) ----------

StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]
SizeStatus = Literal["in_stock", "low_stock", "out_of_stock", "size_not_offered"]


class ProductInfo(BaseModel):
    """Result of get_product_info: everything needed to describe and price one product."""

    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    price: float = Field(description="Current price from the catalogue table.")
    currency: Literal["USD"] = "USD"
    price_display: str = Field(description='Price formatted for the shopper, e.g. "$68.00". Quote this.')


class SizeAvailability(BaseModel):
    size: str
    quantity: int = Field(description="Units on hand for this size, from the inventory table.")
    status: StockStatus


class StockReport(BaseModel):
    """Result of check_stock for one product: live per-size quantities plus a plain-language verdict."""

    product_id: str
    name: str
    overall_status: StockStatus = Field(description="out_of_stock only if every size has quantity 0.")
    total_quantity: int
    sizes: list[SizeAvailability] = Field(description="Every size the product is offered in, XS→XXL.")
    sizes_in_stock: list[str]
    sold_out_sizes: list[str]
    requested_size: str | None = Field(default=None, description="The size the shopper asked about, if any.")
    requested_size_status: SizeStatus | None = None
    requested_size_quantity: int | None = None
    summary: str = Field(description="One-sentence factual verdict to base the reply on.")


class ProductNotFound(BaseModel):
    """Returned instead of guessing when a product_id doesn't exist."""

    product_id: str
    found: Literal[False] = False
    message: str
    suggestions: list["ProductSummary"] = Field(default_factory=list, description="Closest real products by name.")


class SimilarMatch(ProductSummary):
    """A ProductSummary plus why it resembles the base product."""

    reason: str = Field(description='Why it is similar, e.g. "same category; also bulldog, vintage; also gray".')


class SimilarProducts(BaseModel):
    """Result of find_similar_products: in-stock alternatives to one product (Problem 9)."""

    base_product_id: str
    base_name: str
    size: str | None = Field(default=None, description="Every match has this size in stock, if set.")
    matches: list[SimilarMatch]
    note: str = ""


class CatalogueOverview(BaseModel):
    """What the shop carries at a glance. Lets the agent answer "what do you sell?" without a search."""

    total_products: int
    categories: dict[str, int]
    colors: list[str]
    min_price: float
    max_price: float
    sizes: list[str]


# ---------- chat ----------


class ProductCard(BaseModel):
    """Product shown as a clickable card under a chat reply. Stored in chat_messages.products_json."""

    product_id: str
    name: str
    garment_type: str
    price: float
    image_url: str
    colors: list[str]
    sizes_in_stock: list[str]
    total_stock: int


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


PageType = Literal["home", "products", "product", "about", "login", "signup", "other"]


class PageContext(BaseModel):
    """Sent by the widget with every message: where the shopper is. Untrusted; the server resolves ids itself."""

    path: str = Field(default="/", max_length=200)
    page: PageType = "other"
    product_id: str | None = Field(default=None, max_length=120, description="Set on /products/:productId.")
    results_title: str | None = Field(default=None, max_length=60, description="Chat results shown on /products.")
    results_filters: list[str] = Field(default_factory=list, max_length=8)
    preferred_size: str | None = Field(default=None, pattern="^(XS|S|M|L|XL|XXL)$", description='The "My size" filter.')


class ChatRequest(BaseModel):
    """POST /api/chat body. `history` is used only for guests; logged-in users' history comes from the DB."""

    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    page: PageContext | None = None


# ---------- customer memory (Problem 8) ----------


class CustomerProfile(BaseModel):
    """What the agent knows about the logged-in shopper. Never includes password_hash or other users' data."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Account creation date, YYYY-MM-DD.")
    saved_messages: int = Field(description="How many chat messages this shopper has saved (their memory size).")


class CurrentPage(BaseModel):
    """Server-resolved page context given to the agent: `product` comes from the DB, not from the browser."""

    page: PageType
    path: str
    product: "ProductInfo | None" = None
    results_title: str | None = None
    results_filters: list[str] = Field(default_factory=list)
    preferred_size: str | None = None


class PastChatMatch(BaseModel):
    """One earlier message found by recall_past_chats."""

    when: str
    role: str
    content: str = Field(description="Message text, trimmed to 300 characters.")
    viewing: str | None = Field(default=None, description="Product page the shopper was on at the time, if any.")
    products_mentioned: list[str] = Field(default_factory=list, description="Names of products shown with that reply.")


class PastChats(BaseModel):
    """Result of recall_past_chats."""

    logged_in: bool
    matches: list[PastChatMatch] = Field(default_factory=list)
    note: str = ""


class PageSearch(BaseModel):
    """Part of the agent's output: the catalogue search whose full results should appear on the website."""

    title: str = Field(max_length=60, description='Short heading for the page, e.g. "Hoodies" or "Gray tees under $40".')
    query: str = Field(default="", description="Keywords (same meaning as search_products). Empty when filters say it all.")
    category: str | None = Field(default=None, description="hoodie, crewneck, t-shirt, quarter-zip or jacket.")
    color: str | None = None
    size: str | None = Field(default=None, description="Only items with this size in stock.")
    max_price: float | None = None
    min_price: float | None = None


class PageResults(BaseModel):
    """Sent to the website: every product matching the agent's PageSearch, rebuilt from the database."""

    title: str
    filters: list[str] = Field(description='Human-readable filter chips, e.g. ["hoodie", "M", "under $60"].')
    products: list[Product]


class ChatReply(BaseModel):
    """POST /api/chat response. Also the shape of GET /api/chat/history items."""

    role: str = "assistant"
    content: str
    products: list[ProductCard] = Field(default_factory=list)
    page_results: PageResults | None = Field(default=None, description="Present when the page should show search results.")
    suggestions: list[str] = Field(default_factory=list, description="Tappable follow-ups for the latest reply (Problem 9).")


class ShopReply(BaseModel):
    """The agent's structured output (PydanticAI output_type)."""

    message: str = Field(description="Reply to the shopper in Markdown. Friendly, concise, Campus Customs voice.")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="product_id values (copied exactly from tool results) to show as product cards, best first. "
        "Empty if no specific products are being recommended.",
    )
    page_search: PageSearch | None = Field(
        default=None,
        description="Set when the shopper is browsing a type of item (e.g. 'what hoodies do you have?'): the search "
        "whose full results the website should show as product cards. Null for specific-item, stock or small-talk questions.",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 short next steps written as the shopper would type them (each under 40 characters), "
        'e.g. "Check size M", "Show only under $50", "Similar in gray". Empty for off-topic or refused requests.',
    )


# ---------- audit trail (Problem 12) ----------

AuditEvent = Literal["run_start", "tool_call", "tool_retry", "output_retry", "final"]
StopReason = Literal["final_result", "usage_limit", "content_filter", "model_error"]


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json: a step of the agent loop, appended and never rewritten."""

    time: str = Field(description="UTC ISO-8601 timestamp of the step.")
    run_id: str = Field(description="Groups every entry from one chat message (one agent run).")
    iteration: int = Field(description="Agent-loop step: 0 = run start, then 1, 2, … per model response.")
    event: AuditEvent
    actor: str = Field(description='"guest" or "user:<id>". Never an email or name.')
    page: str | None = Field(default=None, description="Page path the shopper was on (validated).")
    tool_name: str | None = None
    tool_args: str | None = Field(default=None, description="Short JSON of the tool arguments (≤ 240 chars, redacted).")
    result: str | None = Field(default=None, description="Short summary of the tool result or final reply (≤ 240 chars).")
    stop_reason: StopReason | None = Field(default=None, description="Why the run ended (only on the final entry).")
    usage: dict[str, int] | None = Field(default=None, description="Model requests / tool calls / tokens (final entry).")


@dataclass
class ShopDeps:
    """Per-request context passed to tools and dynamic instructions (PydanticAI deps).

    Built by main.chat from the session cookie (customer) and the widget's page context (page).
    """

    customer: CustomerProfile | None = None  # None = guest
    page: CurrentPage | None = None
