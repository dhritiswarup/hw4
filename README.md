# Campus Customs: Storefront + AI Shopping Assistant (HW4)

A customer website for **Campus Customs** (officially licensed Yale apparel, 57 Broadway, New Haven) with a chat assistant that answers **only from the store's real inventory**.

- **Frontend:** React + Vite + TypeScript (`frontend/`)
- **Backend:** FastAPI (`backend/main.py`), whose brain is a **PydanticAI agent** (OpenAI `gpt-5.6-luna` via Portkey)
- **Agent:** four files under `backend/`: `prompts/prompt.md` (system prompt), `agent.py` (wiring, safety guards, audit trail), `tools.py` (read-only database tools), `models.py` (Pydantic types)

For how everything works (architecture, specs, tools, model fields, safety rules, audit trail), see **[`output/harness.md`](output/harness.md)**.

---

## Repository layout

```
hw4/
├── AI_prompts.md            # prompt log for every problem
├── requirements.txt         # backend Python dependencies
├── .env.example             # template: copy to .env and add your key
├── .gitignore
├── README.md
├── frontend/                # Vite React TypeScript app
├── backend/
│   ├── main.py              # FastAPI app — run with: uvicorn main:app --reload --port 8000
│   ├── agent.py
│   ├── models.py
│   ├── tools.py
│   └── prompts/
│       └── prompt.md
└── output/
    ├── harness.md           # how the system works
    ├── design.md            # Problem 10 design write-up
    ├── usability.md         # Problem 9 usability improvements
    ├── app_check.html       # Problem 11 live-site check (double-click to open)
    ├── app_check_images/    # screenshots linked from app_check.html
    └── audit_trail.json     # append-only log of agent activity
```

**Not in git (local only):** the course **data pack** (`data/campus_customs.db` and `data/products/*.jpg`), your real `.env`, and `node_modules/`, `.venv/` and `dist/`. All are listed in `.gitignore`.

---

## Setup and run

You need **Python 3.12+**, **Node.js 20+**, and a **Portkey API key**.

### 1. Place the data pack

Put the course data pack in a `data/` folder at the project root (next to `backend/` and `frontend/`):

```
hw4/
└── data/
    ├── campus_customs.db     # SQLite: catalogue, inventory, users (+ chat_messages)
    └── products/             # product images referenced by catalogue.image_file_path
```

If you have the zip, extract it into `hw4/` so that it creates `hw4/data/…`. On first start, the backend adds the tables and columns it needs (`sessions`, `chat_messages.page_context`) automatically.

### 2. Add your API key

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
```

Edit `.env` and set `PORTKEY_API_KEY=...`. It stays on your machine, because `.env` is git-ignored.

### 3. Run the backend (terminal 1)

```bash
python -m venv backend/.venv
# Windows:
backend\.venv\Scripts\pip install -r requirements.txt
# macOS / Linux:
backend/.venv/bin/pip install -r requirements.txt

cd backend
# Windows:
.venv\Scripts\uvicorn main:app --reload --port 8000
# macOS / Linux:
.venv/bin/uvicorn main:app --reload --port 8000
```

The API is now at `http://127.0.0.1:8000` (health check: `/api/health`).

### 4. Run the frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` and `/media` to the backend on port 8000, so keep both running.

### 5. Try it

- **Shop:** browse, filter by category, set **My size**, sort, and open a product.
- **Ask CC** (bottom-right) and try:
  - "What hoodies do you have?"
  - "Is this in stock in XL? How much is it?" (on a product page)
  - "Gift for my dad who likes hockey, about $60"
- **Log in** with the seed test account `test@campuscustoms.yale.edu` / `password`, or create an account. Logged-in chats are saved and reloaded.
- Each chat message appends its agent steps to `output/audit_trail.json`.

**Terminal check of the agent** (no frontend needed): `cd backend && .venv/Scripts/python agent.py "gray hoodie in M?"`

---

## Notes

- **Safety:** the assistant only quotes prices and stock from database tools. A code-level validator rejects made-up prices and fake orders or checkouts, and card numbers and passwords are redacted before the model, the database or the logs see them. See `output/harness.md` §7.
- **Windows and OneDrive:** if `--reload` stalls ("Reloading…" with no new "Application startup complete"), stop uvicorn fully and start it again.
- **Fonts:** yale.edu uses the licensed YaleNew and Mallory typefaces. This site loads free look-alikes (EB Garamond, Source Sans 3) from Google Fonts.
