# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural-language query, FitFindr searches mock thrift listings, generates a personalized outfit suggestion, and produces a shareable social-media caption — handling failures at each step gracefully.

---

## Setup

```bash
# 1. Clone or navigate to this repo
cd fitfindr

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env with your Groq API key (free at console.groq.com)
echo "GROQ_API_KEY=your_key_here" > .env

# 5. Run the app
python app.py
# Open the URL shown in your terminal (typically http://localhost:7860)

# Or run CLI tests:
python agent.py

# Or run the test suite:
pytest tests/ -v
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Natural language query (e.g. "vintage graphic tee"). Matched against title, description, style_tags, category, colors, and brand. |
| `size` | `str \| None` | Clothing size (e.g. "M"). `None` means no size filter. |
| `max_price` | `float \| None` | Maximum price ceiling. `None` means no filter. |

**Returns:** `list[dict]` — List of matching listing dicts sorted by relevance score (keyword hit count). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` on no match — never raises an exception.

**Purpose:** Filters the mock listings dataset and surfaces the best matches for the user's query.

---

### `suggest_outfit(new_item, wardrobe)`

| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A single listing dict as returned by `search_listings`. |
| `wardrobe` | `dict` | User wardrobe with keys: `size` (str), `style_preferences` (list[str]), `items` (list[dict]). |

**Returns:** `str` — 2–4 sentence outfit suggestion. If the wardrobe has items, references specific pieces by name. If wardrobe is empty, gives general styling advice for the item's style tags. On LLM failure, returns a descriptive error string.

**Purpose:** Uses the Groq LLM (llama-3.3-70b-versatile) to style the new thrift find with the user's existing clothes.

---

### `create_fit_card(outfit, new_item)`

| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The outfit suggestion from `suggest_outfit`. |
| `new_item` | `dict` | The listing dict — used to reference platform, price, and title in the caption. |

**Returns:** `str` — A 1–3 sentence casual, authentic social-media caption. Outputs vary across runs (temperature=1.0). On empty outfit input, returns an error message string without calling the LLM.

**Purpose:** Generates a shareable caption that sounds like a real person posting a thrift find — something you'd actually put under an Instagram photo.

---

## How the Planning Loop Works

`run_agent()` in `agent.py` implements a sequential conditional flow — it does not call all three tools unconditionally:

```
1. Call search_listings(description, size, max_price)
   → results == [] → set session["error"], RETURN EARLY (no LLM calls made)
   → results != [] → session["selected_item"] = results[0], continue

2. Call suggest_outfit(selected_item, wardrobe)
   → returns error string → set session["error"], RETURN EARLY
   → returns valid string → session["outfit_suggestion"] = result, continue

3. Call create_fit_card(outfit_suggestion, selected_item)
   → session["fit_card"] = result

4. Return completed session
```

**Why this matters:** If a user searches for "designer ballgown, size XXS, under $5", the agent returns an informative error after step 1 and never makes any LLM calls. The behavior of the loop changes based on what each tool returns — it's not a fixed pipeline.

---

## State Management

All state lives in a single `session` dict initialized at the start of `run_agent()` and threaded through each step:

| Key | Type | Set When | Read By |
|---|---|---|---|
| `session["query"]` | str | On init | Logging/display |
| `session["all_results"]` | list | After search_listings | app.py (result count) |
| `session["selected_item"]` | dict \| None | After search_listings | suggest_outfit, create_fit_card |
| `session["outfit_suggestion"]` | str \| None | After suggest_outfit | create_fit_card, app.py |
| `session["fit_card"]` | str \| None | After create_fit_card | app.py |
| `session["error"]` | str \| None | Any failure | app.py (error panel) |

No tool receives the whole session — each receives only the specific values it needs. `app.py` reads the final session to populate the three output panels. State never requires the user to re-enter information between steps.

---

## Error Handling

### search_listings
- **No matches:** Returns `[]`. The agent checks `if not results` immediately, sets `session["error"]` with a message that includes the query, size, and price (e.g., *"No listings found for 'designer ballgown' in size XXS under $5. Try a broader description or higher price."*), and returns early.
- **File read error:** Exception is caught inside the function; returns `[]`, treated the same as no results.
- **Concrete example from testing:** `search_listings("designer ballgown", size="XXS", max_price=5)` → `[]` → agent error message shown, no LLM calls made.

### suggest_outfit
- **Empty wardrobe:** The LLM prompt switches from "pair with your wardrobe pieces" to "give general styling advice" — the agent always gets back useful text.
- **LLM API failure:** Exception is caught, returns `"Could not generate outfit suggestion — please try again."`. The agent checks for this prefix and stops early.
- **Concrete example from testing:** `suggest_outfit(item, get_empty_wardrobe())` → returns 3 sentences of general styling advice referencing the item's style tags. No crash, no empty string.

### create_fit_card
- **Empty outfit string:** Returns `"Error: cannot generate fit card without outfit details."` immediately — no LLM call is made at all. Guard is checked before any API interaction.
- **LLM API failure:** Exception is caught, returns `"Could not generate fit card — please try again."`.
- **Concrete example from testing:** `create_fit_card("", item)` → `"Error: cannot generate fit card without outfit details."` — confirmed with both `""` and `"   "`.

---

## Spec Reflection

**One way the spec helped:** Writing the exact conditional logic for the planning loop in `planning.md` before coding made `run_agent()` almost mechanical to implement. Having "if results == [] → set error → return" written in plain English meant there were no design decisions left to make while coding — just translation.

**One way implementation diverged from spec:** The spec described `suggest_outfit` returning an "error string" that would trigger an early exit. In practice, an empty wardrobe doesn't produce an error — it produces valid general advice. So the early-exit check only fires on actual API failures (strings starting with "Could not"), not on the empty-wardrobe fallback. The empty wardrobe path became a graceful continuation rather than a stop, which is better UX.

---

## AI Usage

**Instance 1 — search_listings implementation:**
I gave Claude the Tool 1 spec block from `planning.md` (exact parameters, return value description, failure mode) and asked it to implement `search_listings()` using `load_listings()`. It produced a keyword-scoring approach using `sum(1 for kw in keywords if kw in searchable)`. I reviewed it and added multi-field search (the initial version only checked `title` and `description` — I expanded it to also cover `style_tags`, `category`, `brand`, and `colors`), and I changed the empty-results return from `None` to `[]` to match the spec.

**Instance 2 — planning loop from diagram:**
I shared the ASCII architecture diagram and the Planning Loop section from `planning.md` with Claude and asked it to implement `run_agent()`. It generated the session dict structure and the three sequential steps. I revised it to store `all_results` in the session (the generated version only stored `selected_item`), and changed the error-string detection from a broad `startswith("Error")` to checking for both `"Could not"` and `"Error"` to cover both failure modes documented in the spec.
