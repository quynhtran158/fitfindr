# FitFindr

**Week 2 Project — AI 201 @ CodePath**

FitFindr is a multi-tool AI agent I built for the Week 2 project in CodePath's AI course. The idea came from a real problem: thrifting involves a ton of mental work — searching across apps, picturing how something fits with what you already own, deciding if the price is worth it. I wanted to build something that actually helps with that whole process, not just the search part.

The agent takes a natural-language query, searches a mock dataset of secondhand listings, uses an LLM to suggest how to style the find with your existing wardrobe, then generates a shareable caption for it — like something you'd actually post. Each step passes its output to the next, and if anything goes wrong (no results, empty wardrobe, API failure), the agent handles it gracefully instead of crashing.

---

## How It Works

1. **Search** — You describe what you're looking for (e.g. "vintage graphic tee, size M, under $30"). The agent filters the listings by keywords, size, and price and picks the best match.
2. **Style** — It takes that item and your wardrobe and asks the LLM to suggest a complete outfit using pieces you already own. If you haven't shared your wardrobe, it gives general styling advice instead.
3. **Fit card** — Finally it generates a short, casual caption — the kind of thing you'd put under an Instagram post of the outfit.

If step 1 returns nothing, the agent tells you what to try differently and stops there — it doesn't keep going with empty data.

---

## Setup

```bash
# Clone the repo
git clone https://github.com/quynhtran158/fitfindr.git
cd fitfindr

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Add your Groq API key (free at console.groq.com — no credit card needed)
echo "GROQ_API_KEY=your_key_here" > .env

# Run the app
python app.py
# Opens at http://localhost:7860

# Or test from the command line
python agent.py

# Or run the test suite
pytest tests/ -v
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

| Parameter | Type | Description |
|---|---|---|
| `description` | `str` | Natural language query — matched against title, description, style_tags, category, colors, and brand |
| `size` | `str \| None` | Clothing size (e.g. "M") — `None` means no filter |
| `max_price` | `float \| None` | Price ceiling — `None` means no filter |

**Returns:** `list[dict]` — Matching listings sorted by relevance score. Each item has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` on no match, never throws.

---

### `suggest_outfit(new_item, wardrobe)`

| Parameter | Type | Description |
|---|---|---|
| `new_item` | `dict` | A listing dict from `search_listings` |
| `wardrobe` | `dict` | User wardrobe: `size`, `style_preferences`, `items` list |

**Returns:** `str` — 2–4 sentences of outfit advice. If the wardrobe has items, it references them by name. If empty, falls back to general styling tips. Returns a descriptive error string on API failure.

---

### `create_fit_card(outfit, new_item)`

| Parameter | Type | Description |
|---|---|---|
| `outfit` | `str` | The suggestion from `suggest_outfit` |
| `new_item` | `dict` | The listing dict — used to pull platform, price, title into the caption |

**Returns:** `str` — A 1–3 sentence caption that sounds like a real person posting a thrift find. Runs at temperature 1.0 so the output varies each time. Guards against empty outfit input before touching the LLM.

---

## Planning Loop

The agent doesn't call all three tools in a fixed sequence every time. It checks what came back before deciding what to do next:

```
1. search_listings(description, size, max_price)
   → no results  →  set error message, return early (no LLM calls at all)
   → has results →  store selected_item, continue

2. suggest_outfit(selected_item, wardrobe)
   → API error   →  set error message, return early
   → got text    →  store outfit_suggestion, continue

3. create_fit_card(outfit_suggestion, selected_item)
   → store fit_card, return completed session
```

The branching is what makes it an agent rather than a script. An impossible query like "designer ballgown, size XXS, under $5" stops after step 1 and tells you exactly what to adjust — it never makes any LLM calls.

---

## State Management

Everything travels through a single `session` dict that gets built up across the three steps:

| Key | What it holds | Who sets it | Who reads it |
|---|---|---|---|
| `session["query"]` | original description | init | display |
| `session["all_results"]` | full search results | after search | app.py |
| `session["selected_item"]` | top matching listing | after search | suggest_outfit, create_fit_card |
| `session["outfit_suggestion"]` | LLM styling text | after suggest | create_fit_card, app.py |
| `session["fit_card"]` | generated caption | after fit card | app.py |
| `session["error"]` | error message if any step fails | any failure | app.py |

Each tool only receives the specific values it needs — nothing gets the whole session. The user never has to re-enter anything between steps.

---

## Error Handling

**search_listings**
- No matches → returns `[]`, agent sets a message like *"No listings found for 'designer ballgown' in size XXS under $5. Try a broader description or higher price."* and stops.
- File read error → caught inside the function, treated as empty results.
- Tested with: `search_listings("designer ballgown", size="XXS", max_price=5)` → `[]`, no exception.

**suggest_outfit**
- Empty wardrobe → prompt switches from "pair with your wardrobe" to "give general styling advice." Always returns something useful, never crashes.
- LLM API failure → caught, returns `"Could not generate outfit suggestion — please try again."` Agent checks for this and stops early.
- Tested with: `suggest_outfit(item, get_empty_wardrobe())` → 3 sentences of styling advice, no error.

**create_fit_card**
- Empty outfit string → returns `"Error: cannot generate fit card without outfit details."` immediately, before any API call.
- LLM API failure → caught, returns `"Could not generate fit card — please try again."`.
- Tested with: `create_fit_card("", item)` and `create_fit_card("   ", item)` — both return the error string.

---

## Spec Reflection

**What helped:** Writing out the exact conditional logic in `planning.md` before touching any code made the implementation feel straightforward. Having the branches spelled out in plain English — "if results is empty, set error, return early" — meant I wasn't making design decisions while coding, just translating them.

**Where it diverged:** I originally planned for an empty wardrobe to trigger an early exit (same as an API failure). In practice it made more sense to keep going with general styling advice instead — stopping because someone didn't share their wardrobe felt unnecessarily frustrating. So the early-exit check only fires on actual failures, not on the empty-wardrobe fallback.

---

## AI Usage

This project required documenting how I used AI tools, so here are two specific instances:

**search_listings:** I wrote out the full spec for this tool (inputs, return type, failure mode) and used it as a prompt to generate the initial implementation. The output used a keyword-scoring approach I liked, but it only searched `title` and `description` — I added `style_tags`, `category`, `brand`, and `colors` to the searchable fields, and changed the no-results return from `None` to `[]` to match the spec.

**planning loop:** I used the ASCII architecture diagram from `planning.md` as context and asked for help implementing `run_agent()`. The generated version had the right shape but only stored `selected_item` in the session — I added `all_results` so the UI could show the full result count, and tightened the error-string detection to check for both `"Could not"` and `"Error"` prefixes to cover all the failure modes I'd documented.
