"""
Utility functions for loading FitFindr data.
Provides load_listings(), get_example_wardrobe(), and get_empty_wardrobe().
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_listings() -> list[dict]:
    """Load all listings from data/listings.json.

    Returns:
        list[dict]: All listing records. Each record contains fields:
            id, title, description, category, style_tags, size, condition,
            price, colors, brand, platform.
    """
    path = os.path.join(DATA_DIR, "listings.json")
    with open(path, "r") as f:
        return json.load(f)


def get_example_wardrobe() -> dict:
    """Return a pre-filled example wardrobe for testing.

    Returns:
        dict with keys:
            - size (str): user's clothing size
            - style_preferences (list[str]): user's overall style tags
            - items (list[dict]): wardrobe items with id, title, category,
              style_tags, colors, fit_notes
    """
    schema_path = os.path.join(DATA_DIR, "wardrobe_schema.json")
    with open(schema_path, "r") as f:
        schema = json.load(f)
    return schema["example_wardrobe"]


def get_empty_wardrobe() -> dict:
    """Return an empty wardrobe structure for testing.

    Returns:
        dict with keys:
            - size (None)
            - style_preferences ([])
            - items ([])
    """
    schema_path = os.path.join(DATA_DIR, "wardrobe_schema.json")
    with open(schema_path, "r") as f:
        schema = json.load(f)
    return schema["empty_wardrobe"]
