"""Works out which statement lines a question is asking about.

The request normaliser asks a fast model for the metrics in a prompt. When the
model returns none, the request used to fall back to total assets — so a
question about paid-in capital was answered, confidently and with no warning,
by looking up a metric nobody asked for.

The canonical catalog already names every line in Turkish, so the question can
be resolved against it directly. Matching is deliberately strict: a line counts
only when the question actually contains its name or its code. An unresolved
question is better handled by the caller than by guessing a metric.
"""

import re

# Suffixes Turkish attaches to a noun, stripped so that "özkaynakları" and
# "özkaynaklar" resolve to the same catalog line.
_SUFFIXES = (
    "larının",
    "lerinin",
    "ları",
    "leri",
    "sının",
    "sinin",
    "ının",
    "inin",
    "unun",
    "ünün",
    "nın",
    "nin",
    "nun",
    "nün",
    "ları",
    "leri",
    "sı",
    "si",
    "su",
    "sü",
    "ı",
    "i",
    "u",
    "ü",
)


def _fold(text: str) -> str:
    """Lower-case and strip punctuation so wording differences stop mattering."""
    return re.sub(r"[^0-9a-zçğıöşü]+", " ", text.casefold()).strip()


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _stemmed(text: str) -> str:
    return " ".join(_stem(word) for word in _fold(text).split())


def resolve_metric_codes(prompt: str, catalog: list[tuple[str, str]]) -> list[str]:
    """Catalog codes the prompt names, longest name first.

    `catalog` is (metric_code, canonical_name). A code is returned when the
    prompt contains its canonical name or the code itself. Longer names are
    tested first so "Net Faiz Geliri" is preferred over a shorter line whose
    name is contained inside it.
    """
    if not prompt or not catalog:
        return []

    folded = _fold(prompt)
    stemmed = _stemmed(prompt)
    resolved: list[str] = []

    for code, name in sorted(catalog, key=lambda row: len(row[1] or ""), reverse=True):
        if code in resolved:
            continue
        # Folding turns the code's underscores into spaces too, so a prompt
        # quoting TOTAL_ASSETS still matches.
        if _fold(code) in folded:
            resolved.append(code)
            continue
        if not name:
            continue
        if _fold(name) in folded or _stemmed(name) in stemmed:
            resolved.append(code)

    return resolved
