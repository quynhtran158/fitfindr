"""
FitFindr tools — the three callable functions the planning loop orchestrates.
"""

import os
from groq import Groq
from dotenv import load_dotenv
from utils.data_loader import load_listings

load_dotenv()

_groq_client = None


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set in environment / .env file")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ---------------------------------------------------------------------------
# Tool 1: search_listings
# ---------------------------------------------------------------------------

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """Search the mock listings dataset and return matching items.

    Filtering logic:
    - description: matched (case-insensitive) against title, description,
      style_tags, category, and brand of each listing.
    - size: if provided, only listings whose size matches (case-insensitive) are kept.
    - max_price: if provided, only listings with price <= max_price are kept.

    Results are sorted descending by relevance score (number of keyword hits).

    Args:
        description (str): Natural language query, e.g. "vintage graphic tee".
        size (str | None): Clothing size e.g. "M". None means no filter.
        max_price (float | None): Price ceiling. None means no filter.

    Returns:
        list[dict]: Matching listing dicts. Empty list if nothing matches.
                    Never raises an exception.
    """
    try:
        listings = load_listings()
    except Exception:
        return []

    keywords = [kw.lower() for kw in description.split() if kw.strip()]

    results = []
    for item in listings:
        # Size filter
        if size is not None and item.get("size", "").lower() != size.lower():
            continue

        # Price filter
        if max_price is not None and item.get("price", 0) > max_price:
            continue

        # Keyword relevance score
        searchable = " ".join([
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            item.get("brand", ""),
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
        ]).lower()

        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            results.append((score, item))

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results]


# ---------------------------------------------------------------------------
# Tool 2: suggest_outfit
# ---------------------------------------------------------------------------

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """Suggest outfit combinations using a new item and the user's wardrobe.

    If the wardrobe has items, the LLM is asked to reference specific wardrobe
    pieces. If the wardrobe is empty, the LLM is asked for general styling
    advice based on the item's style tags.

    Args:
        new_item (dict): A listing dict (id, title, description, style_tags,
                         colors, condition, price, platform, etc.).
        wardrobe (dict): User wardrobe with keys:
                         - size (str | None)
                         - style_preferences (list[str])
                         - items (list[dict])  — may be empty

    Returns:
        str: A 2–4 sentence outfit suggestion. On LLM error returns a
             descriptive error message string — never raises an exception.
    """
    try:
        client = _get_groq_client()
    except RuntimeError as e:
        return f"Could not generate outfit suggestion: {e}"

    item_name = new_item.get("title", "the item")
    item_tags = ", ".join(new_item.get("style_tags", []))
    item_colors = ", ".join(new_item.get("colors", []))
    item_desc = new_item.get("description", "")

    wardrobe_items = wardrobe.get("items", [])
    style_prefs = ", ".join(wardrobe.get("style_preferences", [])) or "no specific style"

    if wardrobe_items:
        wardrobe_text = "\n".join(
            f"- {w['title']} ({w['category']}, {', '.join(w.get('colors', []))})"
            f"{': ' + w.get('fit_notes', '') if w.get('fit_notes') else ''}"
            for w in wardrobe_items
        )
        prompt = (
            f"You are a personal stylist helping someone style a thrifted piece.\n\n"
            f"New item: {item_name}\n"
            f"Description: {item_desc}\n"
            f"Style tags: {item_tags}\n"
            f"Colors: {item_colors}\n\n"
            f"Their wardrobe:\n{wardrobe_text}\n\n"
            f"Their style preferences: {style_prefs}\n\n"
            f"Suggest 1–2 complete outfit combinations using specific pieces from their wardrobe. "
            f"Be concrete — name the pieces and explain why they work together. "
            f"Keep it to 2–4 sentences, casual and direct."
        )
    else:
        prompt = (
            f"You are a personal stylist helping someone style a thrifted piece.\n\n"
            f"New item: {item_name}\n"
            f"Description: {item_desc}\n"
            f"Style tags: {item_tags}\n"
            f"Colors: {item_colors}\n\n"
            f"The user hasn't shared their wardrobe yet. Give them 2–3 sentences of general "
            f"styling advice for this specific item — what kinds of bottoms, shoes, or layers "
            f"would it work well with, and what vibe does it lean into?"
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate outfit suggestion — please try again. ({e})"


# ---------------------------------------------------------------------------
# Tool 3: create_fit_card
# ---------------------------------------------------------------------------

def create_fit_card(outfit: str, new_item: dict) -> str:
    """Generate a short, shareable social-media caption for the outfit.

    Args:
        outfit (str): The outfit suggestion returned by suggest_outfit.
        new_item (dict): The listing dict for the thrifted piece
                         (used to reference platform, price, title).

    Returns:
        str: A 1–3 sentence caption that sounds authentic and casual —
             the kind of thing someone would caption an Instagram post with.
             Returns a descriptive error message string on failure —
             never raises an exception.
    """
    if not outfit or not outfit.strip():
        return "Error: cannot generate fit card without outfit details."

    item_name = new_item.get("title", "this piece")
    platform = new_item.get("platform", "a thrift app")
    price = new_item.get("price", "")
    price_str = f"${price:.0f}" if isinstance(price, (int, float)) else ""

    try:
        client = _get_groq_client()
    except RuntimeError as e:
        return f"Could not generate fit card: {e}"

    prompt = (
        f"You are writing a short, authentic Instagram caption for a thrift find.\n\n"
        f"The thrifted item: {item_name}{' from ' + platform if platform else ''}"
        f"{' for ' + price_str if price_str else ''}.\n"
        f"How it's being styled: {outfit}\n\n"
        f"Write a 1–3 sentence caption. It should sound like a real person posting — "
        f"casual, a little proud of the find, specific about the piece. "
        f"You can mention the platform and price naturally. "
        f"Vary your tone and wording; do not start with 'I'. "
        f"No hashtags — just the caption."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate fit card — please try again. ({e})"
