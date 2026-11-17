import re
from collections import Counter

STOPWORDS = frozenset(
    """
    a about above after again all also am an and any are as at be because been before
    being below between both but by can could did do does doing down during each few
    for from further had has have having he her here hers him his how i if in into is
    it its itself just me more most my no nor not now of off on once only or other our
    out over own same she should so some such than that the their theirs them then
    there these they this those through to too under until up very was we were what
    when where which while who whom why will with would you your yours
    """.split()
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def split_sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in _SENTENCE_SPLIT.split(flat) if s.strip()]


def _content_words(text: str) -> list[str]:
    words = (w.lower() for w in _WORD.findall(text))
    return [w for w in words if w not in STOPWORDS]


def top_keywords(text: str, limit: int = 10) -> list[str]:
    counts = Counter(_content_words(text))
    return [word for word, _ in counts.most_common(limit)]


def summarize(text: str, max_sentences: int = 5) -> str:
    sentences = split_sentences(text)

    # Keep reasonable-length, unique sentences.
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()
    for index, sentence in enumerate(sentences):
        key = sentence.lower()
        if key in seen or not 6 <= len(sentence.split()) <= 60:
            continue
        seen.add(key)
        candidates.append((index, sentence))

    if not candidates:
        return " ".join(sentences[:max_sentences])

    frequency = Counter(w for _, s in candidates for w in _content_words(s))
    if not frequency:
        return " ".join(s for _, s in candidates[:max_sentences])
    highest = max(frequency.values())

    scored: list[tuple[float, int, str]] = []
    for index, sentence in candidates:
        words = _content_words(sentence)
        if not words:
            continue
        score = sum(frequency[w] / highest for w in words) / len(words) ** 0.5
        scored.append((score, index, sentence))

    best = sorted(scored, key=lambda item: item[0], reverse=True)[:max_sentences]
    best.sort(key=lambda item: item[1])  # restore document order
    return " ".join(sentence for _, _, sentence in best)