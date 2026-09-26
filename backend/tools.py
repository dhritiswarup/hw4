"""Catalogue access for the API routes and the tools the shop agent can call.

Every query opens the database read-only: neither the agent nor the product API can change stock or users.
"""

import json
import re
import sqlite3
from pathlib import Path

from pydantic_ai import RunContext

from models import (
    CatalogueOverview,
    PastChatMatch,
    PastChats,
    ShopDeps,
    SimilarMatch,
    SimilarProducts,
    PageResults,
    PageSearch,
    Product,
    ProductCard,
    ProductDetail,
    ProductInfo,
    ProductNotFound,
    ProductSummary,
    SizeAvailability,
    SizeStock,
    StockReport,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
MAX_SEARCH_RESULTS = 10

# Shopper-friendly category -> regex over the ~22 raw garment_type values (same grouping as the Products page).
CATEGORIES = {
    "hoodie": r"hood",
    "crewneck": r"crew(neck)?|mockneck",
    "t-shirt": r"t-shirt|performance shirt",
    "quarter-zip": r"quarter-zip",
    "jacket": r"jacket",
}

# Shopper words -> words that actually appear in the catalogue.
SYNONYMS = {
    "tee": ["t-shirt"],
    "tees": ["t-shirt"],
    "tshirt": ["t-shirt"],
    "shirt": ["t-shirt", "performance shirt"],
    "hoody": ["hoodie"],
    "hoodies": ["hoodie"],
    "sweatshirt": ["sweatshirt", "hoodie", "crewneck"],
    "sweater": ["sweater", "crewneck", "sweatshirt"],
    "crew": ["crew"],
    "zip": ["zip"],
    "quarterzip": ["quarter-zip"],
    "grey": ["gray"],
    "blue": ["blue", "navy"],
    "dog": ["bulldog"],
    "handsome": ["bulldog"],
    "harvard": ["harvard", "the game"],
}
STOPWORDS = {"a", "an", "the", "and", "or", "for", "with", "in", "of", "do", "you", "have", "any", "me", "show", "some", "i", "want", "looking", "yale"}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- shared loaders (used by API routes and tools) ----------

def _sorted_stock(rows) -> list[SizeStock]:
    rank = {s: i for i, s in enumerate(SIZE_ORDER)}
    stock = [SizeStock(size=r["size"], quantity=r["quantity"]) for r in rows]
    return sorted(stock, key=lambda s: rank.get(s.size, len(rank)))


def load_products() -> list[ProductDetail]:
    """All products with per-size stock, ordered by name."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
        stock: dict[str, list] = {}
        for s in conn.execute("SELECT product_id, size, quantity FROM inventory"):
            stock.setdefault(s["product_id"], []).append(s)
    products = []
    for r in rows:
        inv = _sorted_stock(stock.get(r["product_id"], []))
        products.append(
            ProductDetail(
                product_id=r["product_id"],
                name=r["name"],
                garment_type=r["garment_type"],
                description=r["description"],
                colors=json.loads(r["colors"]),
                search_tags=json.loads(r["search_tags"]),
                image_url=f"/media/{r['image_file_path']}",
                price=r["price"],
                total_stock=sum(s.quantity for s in inv),
                sizes_in_stock=[s.size for s in inv if s.quantity > 0],
                size_stock={s.size: s.quantity for s in inv},
                inventory=inv,
            )
        )
    return products


def load_product(product_id: str) -> ProductDetail | None:
    return next((p for p in load_products() if p.product_id == product_id), None)


def as_product(p: ProductDetail) -> Product:
    return Product(**p.model_dump(exclude={"inventory"}))


def sizes_in_stock(p: ProductDetail) -> list[str]:
    return [s.size for s in p.inventory if s.quantity > 0]


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Cards for the given ids, in order. Unknown ids are silently dropped, so the agent can't invent products."""
    by_id = {p.product_id: p for p in load_products()}
    cards, seen = [], set()
    for pid in product_ids:
        p = by_id.get(pid)
        if p is None or pid in seen:
            continue
        seen.add(pid)
        cards.append(
            ProductCard(
                product_id=p.product_id,
                name=p.name,
                garment_type=p.garment_type,
                price=p.price,
                image_url=p.image_url,
                colors=p.colors,
                sizes_in_stock=sizes_in_stock(p),
                total_stock=p.total_stock,
            )
        )
    return cards


def category_of(garment_type: str) -> str:
    return next((c for c, rx in CATEGORIES.items() if re.search(rx, garment_type, re.I)), "other")


# ---------- agent tools ----------

def _terms(query: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9\-]+", query.lower()) if w not in STOPWORDS]
    terms: list[str] = []
    for w in words:
        terms.extend(SYNONYMS.get(w, [w.rstrip("s") if len(w) > 3 and w.endswith("s") else w]))
    return terms


def _summary(p: ProductDetail) -> ProductSummary:
    return ProductSummary(
        product_id=p.product_id,
        name=p.name,
        garment_type=p.garment_type,
        price=p.price,
        colors=p.colors,
        sizes_in_stock=sizes_in_stock(p),
        total_stock=p.total_stock,
        short_description=p.description.split(". ")[0].rstrip(".") + ".",
    )


def search_products(
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    limit: int = 8,
) -> list[ProductSummary]:
    """Search the Campus Customs catalogue. Use this before recommending anything.

    Args:
        query: Free-text keywords, e.g. "bulldog", "hockey", "Harvard game", "Branford". Can be empty to browse with filters only.
        category: One of "hoodie", "crewneck", "t-shirt", "quarter-zip", "jacket".
        color: A color to match, e.g. "navy", "gray", "white".
        size: Only return products with this size in stock (XS, S, M, L, XL, XXL; "medium" etc. also work). For browsing only:
            when the shopper names a specific product, leave this empty and check each hit's
            sizes_in_stock, so sold-out look-alikes aren't hidden.
        max_price: Maximum price in USD.
        min_price: Minimum price in USD.
        limit: Number of results to return (1-10).

    Returns:
        Matching products, best match first. An empty list means nothing in the catalogue matches.
    """
    limit = max(1, min(limit, MAX_SEARCH_RESULTS))
    hits = find_products(query, category, color, size, max_price, min_price)
    return [_summary(p) for p in hits[:limit]]


def find_products(
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    size: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
) -> list[ProductDetail]:
    """Every catalogue match, best first. Shared by the search tool (capped) and the page results (uncapped)."""
    terms = _terms(query)
    size = normalize_size(size) if size else None
    color_terms = _terms(color) if color else []
    results: list[tuple[float, ProductDetail]] = []

    for p in load_products():
        if category and category_of(p.garment_type) != category.lower().strip():
            continue
        if max_price is not None and p.price > max_price:
            continue
        if min_price is not None and p.price < min_price:
            continue
        if size and size not in sizes_in_stock(p):
            continue
        colors = " ".join(p.colors).lower()
        if color_terms and not any(t in colors for t in color_terms):
            continue

        score = 0.0
        if terms:
            fields = [
                (p.name.lower(), 3.0),
                (" ".join(p.search_tags).lower(), 2.0),
                (p.garment_type.lower(), 2.0),
                (colors, 1.5),
                (p.description.lower(), 1.0),
            ]
            for t in terms:
                score += sum(w for text, w in fields if t in text)
            if score == 0:
                continue
        # Prefer items that are actually available.
        score += min(p.total_stock, 100) / 1000
        results.append((score, p))

    results.sort(key=lambda sp: sp[0], reverse=True)
    return [p for _, p in results]


# ---------- similar in-stock alternatives (Problem 9) ----------

# Tags on almost every product; sharing them says nothing about similarity.
GENERIC_TAGS = {
    "yale", "yale university", "campus customs", "college apparel", "college merch", "yale merch",
    "college", "university", "apparel", "yale apparel", "collegiate", "school spirit",
}
# Garment/color words are already scored via category and colors; skip them so shared tags mean shared themes.
STRUCTURAL_WORDS = {
    "hoodie", "hood", "hooded", "hoody", "pullover", "sweatshirt", "crewneck", "crew-neck", "t-shirt", "tee", "shirt",
    "long", "short", "sleeve", "graphic", "logo", "drawstring", "pocket", "kangaroo", "ribbed", "cuffs", "zip",
    "navy", "blue", "gray", "grey", "white", "black", "heather", "dark", "light", "charcoal", "red", "gold",
}
MAX_SIMILAR = 6


def _tag_words(p: ProductDetail) -> set[str]:
    words: set[str] = set()
    for tag in p.search_tags:
        t = tag.lower().strip()
        if t in GENERIC_TAGS:
            continue
        words.update(
            w for w in re.findall(r"[a-z0-9\-]+", t) if w not in STOPWORDS and w not in STRUCTURAL_WORDS and len(w) > 2
        )
    return words


def find_similar_products(
    product_id: str,
    size: str | None = None,
    max_price: float | None = None,
    limit: int = 4,
) -> SimilarProducts | ProductNotFound:
    """Find IN-STOCK products similar to one product, e.g. when it is sold out in the shopper's size.

    Call this when check_stock says the item or requested size is out of stock, or when the shopper asks for
    "something like this" / "other options". Every match is in stock (in `size`, if given).

    Args:
        product_id: The product to find alternatives for (exact product_id).
        size: Only return matches with this size in stock (XS-XXL; "medium" etc. work). Use the shopper's size.
        max_price: Optional price ceiling in USD.
        limit: Number of alternatives (1-6).
    """
    products = load_products()
    base = next((p for p in products if p.product_id == product_id), None)
    if base is None:
        return _not_found(product_id)
    limit = max(1, min(limit, MAX_SIMILAR))
    size = normalize_size(size) if size else None
    base_cat = category_of(base.garment_type)
    base_tags = _tag_words(base)
    base_colors = {c.lower() for c in base.colors}

    scored: list[tuple[float, ProductDetail, str]] = []
    for p in products:
        if p.product_id == base.product_id or p.total_stock <= 0:
            continue
        if size and size not in sizes_in_stock(p):
            continue
        if max_price is not None and p.price > max_price:
            continue
        reasons, score = [], 0.0
        if category_of(p.garment_type) == base_cat:
            score += 3
            reasons.append("same category")
        shared_tags = sorted(base_tags & _tag_words(p))
        if shared_tags:
            score += len(shared_tags)
            reasons.append("also " + ", ".join(shared_tags[:3]))
        shared_colors = sorted(base_colors & {c.lower() for c in p.colors})
        if shared_colors:
            score += 0.5 * len(shared_colors)
            reasons.append("also " + "/".join(shared_colors[:2]))
        score += max(0.0, 1 - abs(p.price - base.price) / 50)  # similar price
        if score >= 3:  # at least same category, or several shared themes
            scored.append((score, p, "; ".join(reasons)))

    scored.sort(key=lambda t: t[0], reverse=True)
    matches = [SimilarMatch(**_summary(p).model_dump(), reason=why) for _, p, why in scored[:limit]]
    note = "" if matches else "No similar in-stock items found. Suggest browsing the category instead."
    return SimilarProducts(base_product_id=base.product_id, base_name=base.name, size=size, matches=matches, note=note)


# ---------- customer memory (Problem 8) ----------

MAX_RECALL = 8


def recall_past_chats(ctx: RunContext[ShopDeps], query: str = "", limit: int = 5) -> PastChats:
    """Search the logged-in shopper's OWN earlier chat messages (older than what's in this conversation).

    Use when they refer to something from a past visit: "the hoodie you showed me last time",
    "what did I ask about before?". Always scoped to the current shopper; guests have no saved history.

    Args:
        query: Keywords to look for, e.g. "hoodie", "gift", "dad". Empty returns their most recent messages.
        limit: How many matching messages to return (1-8).
    """
    customer = ctx.deps.customer
    if customer is None:
        return PastChats(logged_in=False, note="The shopper is a guest, so there is no saved chat history.")

    limit = max(1, min(limit, MAX_RECALL))
    words = [w for w in re.findall(r"[a-z0-9\-]+", query.lower()) if w not in STOPWORDS][:5]
    sql = "SELECT role, content, products_json, page_context, created_at FROM chat_messages WHERE user_id = ?"
    args: list = [customer.user_id]  # from the session, never from the model
    if words:
        sql += " AND (" + " OR ".join("LOWER(content) LIKE ?" for _ in words) + ")"
        args += [f"%{w}%" for w in words]
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)

    with connect() as conn:
        rows = conn.execute(sql, args).fetchall()
    matches = []
    for r in rows:
        products = json.loads(r["products_json"]) if r["products_json"] else []
        page = json.loads(r["page_context"]) if r["page_context"] else {}
        content = r["content"]
        matches.append(
            PastChatMatch(
                when=r["created_at"],
                role=r["role"],
                content=content if len(content) <= 300 else content[:297] + "...",
                viewing=page.get("product_name"),
                products_mentioned=[p["name"] for p in products if "name" in p],
            )
        )
    note = "" if matches else "No earlier messages matched. Say you don't see that in their history."
    return PastChats(logged_in=True, matches=matches, note=note)


# ---------- page results: chat search shown on the website (Problem 7) ----------

MAX_PAGE_RESULTS = 60


def page_results(search: PageSearch) -> PageResults | None:
    """Re-run the agent's chosen search against the database and return every match for the Products page.

    The agent only picks the filters; the product list itself always comes from the database.
    Returns None when nothing matches, so the page keeps what it was showing.
    """
    hits = find_products(
        search.query, search.category, search.color, search.size, search.max_price, search.min_price
    )[:MAX_PAGE_RESULTS]
    if not hits:
        return None
    filters = {
        "category": search.category,
        "color": search.color,
        "size": normalize_size(search.size) if search.size else None,
        "max_price": f"under ${search.max_price:g}" if search.max_price is not None else None,
        "min_price": f"from ${search.min_price:g}" if search.min_price is not None else None,
        "keywords": search.query.strip() or None,
    }
    return PageResults(
        title=search.title,
        filters=[v for v in filters.values() if v],
        products=[as_product(p) for p in hits],
    )


# ---------- product info + stock lookups (Problem 6) ----------

LOW_STOCK_THRESHOLD = 5  # 1-5 units left counts as "low_stock"
MAX_STOCK_BATCH = 6
SIZE_ALIASES = {
    "xs": "XS", "x-small": "XS", "xsmall": "XS", "extra small": "XS", "extra-small": "XS",
    "s": "S", "small": "S", "sm": "S",
    "m": "M", "medium": "M", "med": "M",
    "l": "L", "large": "L", "lg": "L",
    "xl": "XL", "x-large": "XL", "xlarge": "XL", "extra large": "XL", "extra-large": "XL",
    "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL", "xxlarge": "XXL", "2x": "XXL",
}


def normalize_size(size: str) -> str:
    s = size.strip().lower()
    return SIZE_ALIASES.get(s, size.strip().upper())


def _status(quantity: int) -> str:
    if quantity <= 0:
        return "out_of_stock"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


def _not_found(product_id: str) -> ProductNotFound:
    guesses = search_products(query=product_id.replace("-", " "), limit=3)
    return ProductNotFound(
        product_id=product_id,
        message=f"There is no product with id {product_id!r} in the catalogue. Don't guess its price or stock; "
        "use one of the suggestions or search_products to find the right id.",
        suggestions=guesses,
    )


def get_product_info(product_id: str) -> ProductInfo | ProductNotFound:
    """Look up one product's description, colors and current price in the database.

    Call this whenever the shopper asks what an item is like or how much it costs. Quote `price_display`.

    Args:
        product_id: The exact product_id from a search result.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT product_id, name, garment_type, description, colors, price FROM catalogue WHERE product_id = ?",
            (product_id,),
        ).fetchone()
    if row is None:
        return _not_found(product_id)
    return ProductInfo(
        product_id=row["product_id"],
        name=row["name"],
        garment_type=row["garment_type"],
        description=row["description"],
        colors=json.loads(row["colors"]),
        price=row["price"],
        price_display=f"${row['price']:.2f}",
    )


def _stock_report(conn: sqlite3.Connection, product_id: str, size: str | None) -> StockReport | ProductNotFound:
    product = conn.execute("SELECT name FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    if product is None:
        return _not_found(product_id)
    rows = conn.execute("SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)).fetchall()
    sizes = [SizeAvailability(size=s.size, quantity=s.quantity, status=_status(s.quantity)) for s in _sorted_stock(rows)]
    total = sum(s.quantity for s in sizes)
    in_stock = [s.size for s in sizes if s.quantity > 0]
    sold_out = [s.size for s in sizes if s.quantity <= 0]
    name = product["name"]

    report = StockReport(
        product_id=product_id,
        name=name,
        overall_status="out_of_stock" if total == 0 else _status(total),
        total_quantity=total,
        sizes=sizes,
        sizes_in_stock=in_stock,
        sold_out_sizes=sold_out,
        summary="",
    )
    if size:
        wanted = normalize_size(size)
        match = next((s for s in sizes if s.size == wanted), None)
        report.requested_size = wanted
        if match is None:
            report.requested_size_status = "size_not_offered"
            report.summary = f"{name} is not offered in size {wanted}. Offered sizes: {', '.join(s.size for s in sizes)}."
        else:
            report.requested_size_status = match.status
            report.requested_size_quantity = match.quantity
            if match.quantity <= 0:
                alt = f" Sizes in stock: {', '.join(in_stock)}." if in_stock else " It is sold out in every size."
                report.summary = f"{name} is OUT OF STOCK in size {wanted}.{alt}"
            else:
                few = "only " if match.status == "low_stock" else ""
                report.summary = f"{name} is in stock in size {wanted}: {few}{match.quantity} left."
    elif total == 0:
        report.summary = f"{name} is OUT OF STOCK in every size."
    else:
        detail = ", ".join(f"{s.size}: {s.quantity}" for s in sizes)
        out = f" Sold out: {', '.join(sold_out)}." if sold_out else ""
        report.summary = f"{name} has {total} in stock ({detail}).{out}"
    return report


def check_stock(product_ids: list[str], size: str | None = None) -> list[StockReport | ProductNotFound]:
    """Check live inventory in the database for one or more products, optionally for one size.

    Call this for ANY question about availability or quantities ("do you have it in M?", "how many are left?",
    "which of those come in XXL?"). Never state a stock number that didn't come from this tool.

    Args:
        product_ids: Exact product_id values from search results (1-6 at once).
        size: The size the shopper asked about (XS, S, M, L, XL, XXL; words like "medium" also work). Leave empty for all sizes.
    """
    ids = list(dict.fromkeys(product_ids))[:MAX_STOCK_BATCH]
    with connect() as conn:
        return [_stock_report(conn, pid, size) for pid in ids]


def catalogue_overview() -> CatalogueOverview:
    """A summary of what Campus Customs sells: categories with counts, colors, price range and sizes."""
    products = load_products()
    categories: dict[str, int] = {}
    colors: set[str] = set()
    for p in products:
        c = category_of(p.garment_type)
        categories[c] = categories.get(c, 0) + 1
        colors.update(x.lower() for x in p.colors)
    return CatalogueOverview(
        total_products=len(products),
        categories=categories,
        colors=sorted(colors),
        min_price=min(p.price for p in products),
        max_price=max(p.price for p in products),
        sizes=SIZE_ORDER,
    )
