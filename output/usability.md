# Campus Customs: Usability Improvements (Problem 9)

Four improvements were chosen after using the site and chatbot in Problems 3–8 and noting where shoppers would get stuck: two in the website and two in the agent backend. Each one is described below with what was added, why it helps a Campus Customs shopper or the business, and how it was checked in the running app.

| # | Area | Improvement | Main files |
|---|---|---|---|
| 1 | Front end | Shop by size and sort on the Products page | `frontend/src/pages/Products.tsx`, `frontend/src/preferences.ts`, `backend/models.py` (`Product.sizes_in_stock`) |
| 2 | Front end | Page-aware quick-start chips in the chat | `frontend/src/components/ChatWidget.tsx` |
| 3 | Agent backend | Suggested next steps after every reply | `backend/models.py` (`ShopReply.suggestions`), `backend/agent.py`, `backend/prompts/prompt.md` |
| 4 | Agent backend | `find_similar_products` tool: in-stock alternatives for sold-out items | `backend/tools.py`, `backend/models.py` (`SimilarProducts`), `backend/prompts/prompt.md` |

---

## 1. Front end: shop by size and sort

**What was added**
- A toolbar on the Products page with a **"My size"** selector (Any, XS–XXL) and a **Sort** menu (Featured, Price low→high, Price high→low, Name A–Z).
- When a size is picked, only products **with that size in stock** are shown. Each card also gets a small "M in stock" or "Only 3 left in M" line, so the shopper doesn't have to open every item to check.
- The size is **remembered** in `localStorage`, so it's still set on the next visit. It applies to the full catalogue **and** to results the chatbot puts on the page.
- The chosen size is also sent to the agent in the page context ("Shopper's selected size: M"). "Do you have any hoodies?" then means hoodies in M, without the shopper having to repeat their size.
- To support this, `GET /api/products` now returns `sizes_in_stock` and `size_stock` for each product.

**Why it helps**
- **Shopper:** apparel shopping is size-first. Before, a shopper who wears XL had to open each of the 102 products to find out it was sold out in XL. That's frustrating and slow on a phone. With a size set, every card on the page is something they can actually buy.
- **Shopper:** sorting by price lets a student on a budget find the $32 tees first, while a parent buying a gift can sort high→low to find the $98 jackets.
- **Business:** fewer dead-end clicks means fewer abandoned visits. Showing the low-stock line ("Only 2 left in XL") nudges shoppers to buy before an item sells out.

## 2. Front end: page-aware quick-start chips in the chat

**What was added**
- When the chat opens with no conversation yet, a row of tappable **suggestion chips** appears above the input. Tapping one sends it immediately.
- The chips **change with the page**:
  - Home, About and other pages: "What hoodies do you have?", "Gift ideas for a Yale parent", "Tees under $40", "Anything with a bulldog?"
  - The Products page with chat results showing: "Only show ones in my size", "Sort these by price", "What's most popular?"
  - A product page: "Is this in stock in {my size}?", "What colors does this come in?", "Show me similar items", "How much is this?"

**Why it helps**
- **Shopper:** a blank chat box is intimidating. Many visitors don't know what the bot can do, or how to phrase a question. Chips show the bot's abilities (search, stock, gifts, budget) and turn the first question into one tap. That matters most on mobile, where typing is slow.
- **Shopper:** on a product page, the most common questions (my size? other colors?) are one tap away, and they use the page context from Problem 8, so "this" just works.
- **Business:** more shoppers start a conversation, and conversations lead to product cards and sales. It also steers people toward questions the bot answers well.

## 3. Agent backend: suggested next steps after every reply

**What was added**
- The agent's structured output (`ShopReply`) has a new `suggestions` field: up to **3 short follow-ups written as the shopper would type them**, e.g. "Check size M", "Show only under $50", "Similar in gray".
- `ChatReply.suggestions` carries them to the website, where they appear as chips under the **latest** assistant reply. Tapping one sends it.
- Prompt rules (`prompts/prompt.md`, "Suggested next steps") say suggestions must be grounded in what was just discussed and point to things the shop can actually do. They must never offer something the store doesn't have (no "Show pink hoodies" after saying there are none), and are left empty for off-topic or refused requests.

**Why it helps**
- **Shopper:** after an answer, the natural next step (check my size, narrow by price, see similar) is one tap, so the conversation keeps moving instead of stalling. Shoppers learn follow-up moves they might not have thought of, such as "Show the whole collection on the page".
- **Business:** guided conversations reach a product decision (size confirmed, item in stock) in fewer turns, which means more conversions and fewer model calls per sale.

## 4. Agent backend: `find_similar_products`, in-stock alternatives for sold-out items

**What was added**
- A new agent tool, `find_similar_products(product_id, size=None, max_price=None, limit=4)`. It ranks other products by similarity to a base product:
  - same category (+3)
  - shared distinctive tags, e.g. "bulldog", "hockey", "vintage", "crewneck" (+1 each; generic tags like "Yale" are ignored)
  - shared colors (+0.5 each)
  - similar price (up to +1)
- It **only returns items that are actually in stock**, in the requested size if one is given. Each match comes with a short `reason` ("same category; also bulldog, vintage; also gray").
- Returns a typed `SimilarProducts` result (`models.py`).
- Prompt rules: when `check_stock` says the requested size or item is **out of stock**, or the shopper asks for "something like this", the agent calls `find_similar_products` and offers 1–3 alternatives as product cards, instead of just "sorry, sold out".

**Why it helps**
- **Shopper:** "Sorry, that's sold out in M" was a dead end before. Now the shopper immediately gets real, in-stock look-alikes in their size, with a reason each one is a good substitute.
- **Business:** stockouts become sales of similar items instead of lost customers. Because results only include in-stock items, the bot never recommends another sold-out product.

---

## Verified in the running app

All four were tested in the browser preview against the live backend (`gpt-5.6-luna` via Portkey), and the numbers were cross-checked with SQL against `campus_customs.db`.

| # | Test in the running app | Result |
|---|---|---|
| 1 | Products page, pick **My size = XL** | Count line "**77 of 102** items in stock in XL". An SQL check found 25 products with XL = 0, and 102 − 25 = 77 ✅. Cards show "XL in stock", or amber "Only 2 left in XL" (21 cards). |
| 1 | Sort **Price: low to high** | Starts with $32 tees and ends with the $98 School of Music Fleece Sweater. Prices are in ascending order ✅. |
| 1 | Reload the page | "XL" is still selected (read from `localStorage`) ✅. |
| 1 | Chat results obey the size | After "What hoodies do you have?", the banner reads "**21 of 27** items in stock in XL" ✅. The agent's reply said "strong picks in your XL" because the page context carried the size ✅. |
| 1 | Product page with My size = M | The Crew Left Chest Hoodie page opens with **M preselected** and "Sold out in your size (M). Ask the assistant for similar items in M." ✅ |
| 2 | Open the chat on Products (guest, no conversation) | "TRY" chips: What hoodies do you have? · Gift ideas for a Yale parent · Tees under $40 · Anything with a bulldog? ✅ Tapping one sends it immediately ✅. |
| 2 | Open the chat on a product page (size M) | Chips change to: **Is this in stock in M?** · What colors does this come in? · Show me similar items · How much is this? ✅ The input placeholder is "Ask about this item…". |
| 3 | After "What hoodies do you have?" | Chips under the reply: "Only hoodies in XL", "Show hoodies under $50", "Any bulldog hoodies?" ✅ |
| 3 | After the sold-out answer | "Try the Sailing hoodie", "Check navy hoodies in M", "Show all hoodies in M" ✅. Tapping **Show all hoodies in M** sent it and updated the page to "Hoodies in M · hoodie · M · 21 items". SQL also finds 21 hoodies with M in stock ✅. |
| 3 | Off-topic: "can you write my econ essay?" | Polite decline with `suggestions: []` ✅. The page's quick-start chips show instead. |
| 4 | Product page Crew Left Chest Hoodie, tap "Is this in stock in M?" | Tool log: `check_stock(["crew-left-chest-hoodie"], "M")` → `find_similar_products("crew-left-chest-hoodie", size="M", limit=3)`. Reply: "Sorry, the Crew Left Chest Hoodie is **out of stock in M**. It's available in XS, S, L, XL and XXL. Similar navy left-chest hoodies available in M are Fencing, Sailing and Squash Left Chest Hoodie." All 3 cards list M in stock ✅. |
| 4 | Offline ranking checks | Vintage Bulldog (sold out in XXL) → top match **Vintage Sailor Bulldog** ("also bulldog, vintage"). Ice Hockey Left Chest (sold out in M) → top match **Yale Sports Hoodie Hockey** ("also college, hockey, sports"). Every match has the requested size in stock ✅. |

### Issues found while testing (and fixed)

- **Stale suggestions after navigating.** The agent's chips from the Products page ("Only hoodies in XL") were still shown after the shopper opened a product page, which hid that page's own quick-start chips. The widget now remembers which page a reply was given on (`replyPath`). Once the shopper navigates away, those suggestions are hidden and the new page's starters appear.
- **Noisy similarity reasons.** The first version of `find_similar_products` explained matches with words like "hoodie, hood, drawstring, blue", which describe almost every product. Garment and color words are now excluded from the shared-tag score, since they're already scored through category and colors. The reasons now name real themes ("bulldog, vintage", "hockey", "left chest").
