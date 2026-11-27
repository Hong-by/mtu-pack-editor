"""Portable Korean localisation overlay, imported explicitly by maintainers."""
from functools import lru_cache
from pathlib import Path
import json

PATCH_PATH = Path(__file__).resolve().parent / 'data' / 'gathering_ko.loc.json'


@lru_cache(maxsize=1)
def translations():
    return json.loads(PATCH_PATH.read_text(encoding='utf-8'))['rows']


def overlay(texts):
    return {**texts, **translations()}
