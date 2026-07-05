"""WordNet-backed source: pulls every lemma in a noun/verb subtree, or every
verb in the whole lexicon, as candidate Pictionary items. No network calls
beyond a one-time corpus download (cached locally by nltk).
"""

import io
import zipfile
from pathlib import Path

import nltk
import requests

WORDNET_ZIP_URL = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/wordnet.zip"
NLTK_DATA_DIR = Path.home() / "nltk_data"


def ensure_wordnet() -> None:
    """Make sure the WordNet corpus is available locally.

    Tries nltk's own downloader first; some environments block/timeout its
    default mirror, so this falls back to fetching the same zip directly
    with `requests` and extracting it into ~/nltk_data/corpora.
    """
    try:
        nltk.data.find("corpora/wordnet")
        return
    except LookupError:
        pass

    try:
        nltk.download("wordnet", quiet=True)
        nltk.data.find("corpora/wordnet")
        return
    except Exception:
        pass

    corpora_dir = NLTK_DATA_DIR / "corpora"
    corpora_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(WORDNET_ZIP_URL, timeout=60)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(corpora_dir)
    nltk.data.find("corpora/wordnet")


def _clean(name: str) -> str:
    return name.replace("_", " ").strip()


def hyponym_lemmas(*root_synsets: str) -> list[str]:
    """All lemma names in the full hyponym subtree of each given synset
    (e.g. "artifact.n.01"), deduped case-insensitively across all roots.
    """
    ensure_wordnet()
    from nltk.corpus import wordnet as wn

    seen_lower = set()
    results = []
    for root_name in root_synsets:
        root = wn.synset(root_name)
        stack = [root]
        visited = set()
        while stack:
            synset = stack.pop()
            if synset in visited:
                continue
            visited.add(synset)
            for lemma in synset.lemmas():
                name = _clean(lemma.name())
                if name.lower() not in seen_lower:
                    seen_lower.add(name.lower())
                    results.append(name)
            stack.extend(synset.hyponyms())
    return results


def all_verb_lemmas() -> list[str]:
    """Every lemma name across all verb synsets in WordNet, deduped
    case-insensitively. Used as the "actions" source — WordNet has no
    single "action" root synset the way nouns have "entity.n.01", so verbs
    are collected directly from the full verb POS.
    """
    ensure_wordnet()
    from nltk.corpus import wordnet as wn

    seen_lower = set()
    results = []
    for synset in wn.all_synsets("v"):
        for lemma in synset.lemmas():
            name = _clean(lemma.name())
            if name.lower() not in seen_lower:
                seen_lower.add(name.lower())
                results.append(name)
    return results
