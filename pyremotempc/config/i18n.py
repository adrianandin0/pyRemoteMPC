"""
Internationalization (i18n) Module for pyRemoteMPC.
Loads translation strings from JSON files stored in pyremotempc/config/locales/.
Supports English (en) and Spanish (es).
"""

import os
import json
from typing import Dict

LOCALES_DIR = os.path.join(os.path.dirname(__file__), "locales")
_translations_cache: Dict[str, Dict[str, str]] = {}


def load_locale(lang: str) -> Dict[str, str]:
    lang_code = (lang or "en").strip().lower()
    if lang_code in _translations_cache:
        return _translations_cache[lang_code]

    json_path = os.path.join(LOCALES_DIR, f"{lang_code}.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _translations_cache[lang_code] = data
                return data
        except Exception as e:
            print(f"Failed to load translation file {json_path}: {e}")

    # Fallback to English if file missing
    if lang_code != "en":
        return load_locale("en")

    return {}


def tr(key: str, lang: str = "en") -> str:
    """
    Returns translated string for given key and language code.
    Falls back to English if translation is missing.
    """
    locale_dict = load_locale(lang)
    if key in locale_dict:
        return locale_dict[key]

    # Fallback to English
    if lang != "en":
        en_dict = load_locale("en")
        if key in en_dict:
            return en_dict[key]

    return key
