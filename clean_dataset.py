"""Clean the title and body, keep articles of at least 100 words, and add a label from 8 groups."""

import csv
import html
import re
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).parent / "data" / "articles.csv"
OUTPUT = Path(__file__).parent / "data" / "clean" / "articles.csv"
MIN_WORDS = 100

LABELS = {
    "sports": "sports",
    "soccer": "sports",
    "football": "sports",
    "basketball": "sports",
    "baseball": "sports",
    "hockey": "sports",
    "tennis": "sports",
    "cricket": "sports",
    "rugby": "sports",
    "golf": "sports",
    "cycling": "sports",
    "motor sports": "sports",
    "water sports": "sports",
    "combat sports": "sports",
    "sports betting": "sports",
    "business": "business_finance",
    "finance": "business_finance",
    "economy": "business_finance",
    "personal finance": "business_finance",
    "digital currencies": "business_finance",
    "jobs": "business_finance",
    "shopping": "business_finance",
    "technology": "technology",
    "mobile": "technology",
    "gadgets": "technology",
    "gaming": "technology",
    "virtual reality": "technology",
    "robotics": "technology",
    "internet security": "technology",
    "science": "science_nature",
    "space": "science_nature",
    "physics": "science_nature",
    "geology": "science_nature",
    "paleontology": "science_nature",
    "neuroscience": "science_nature",
    "environment": "science_nature",
    "energy": "science_nature",
    "wildlife": "science_nature",
    "health": "health",
    "medicine": "health",
    "mental health": "health",
    "public health": "health",
    "nutrition": "health",
    "entertainment": "entertainment_culture",
    "celebrities": "entertainment_culture",
    "movies": "entertainment_culture",
    "tv": "entertainment_culture",
    "music": "entertainment_culture",
    "theater": "entertainment_culture",
    "arts-design": "entertainment_culture",
    "travel": "lifestyle",
    "food": "lifestyle",
    "home": "lifestyle",
    "outdoors": "lifestyle",
    "fashion": "lifestyle",
    "beauty": "lifestyle",
    "vehicles": "lifestyle",
    "world": "politics_society",
    "politics": "politics_society",
    "education": "politics_society",
    "higher education": "politics_society",
    "online education": "politics_society",
    "social sciences": "politics_society",
}

FIELDS = [
    "uuid",
    "title",
    "published_at",
    "publisher",
    "original_url",
    "topics",
    "label",
    "body",
]


INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff\u2060\u00ad\ufe0f]")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
HANDLE_RE = re.compile(r"(?<![\w@])@\w{2,}")
EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U00002B00-\U00002BFF"
    "\U00002500-\U0000257F"
    "\U0000231A-\U0000231B"
    "\U000023E9-\U000023FA"
    "]+"
)
PUNCTUATION = str.maketrans(
    {
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u2014": "-",
        "\u2013": "-",
        "\u2010": "-",
        "\u2212": "-",
        "\u2026": "...",
    }
)


def unescape_all(text):
    for _ in range(3):
        unescaped = html.unescape(text)
        if unescaped == text:
            break
        text = unescaped
    return text


def clean_text(text):
    text = INVISIBLE_RE.sub("", text or "")
    text = unescape_all(text)
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)
    text = EMOJI_RE.sub(" ", text)
    text = HANDLE_RE.sub(" ", text)
    text = text.translate(PUNCTUATION)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return text.strip()


def coarse_labels(topics):
    labels = []
    for topic in topics.split("|"):
        topic = topic.strip().lower()
        if not topic:
            continue
        label = LABELS[topic]
        if label not in labels:
            labels.append(label)
    return sorted(labels)


def main():
    kept = []
    skipped_short = 0
    with SOURCE.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            body = clean_text(row["body"])
            if len(body.split()) < MIN_WORDS:
                skipped_short += 1
                continue
            labels = coarse_labels(row["topics"])
            kept.append(
                {
                    **row,
                    "title": clean_text(row["title"]),
                    "body": body,
                    "label": "|".join(labels),
                }
            )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept)

    counts = Counter(row["label"] for row in kept)
    single = sum(count for label, count in counts.items() if "|" not in label)
    print(f"Zapisano: {OUTPUT}")
    print(f"Zostawione: {len(kept)} | Odrzucone (<{MIN_WORDS} słów): {skipped_short}")
    print(f"Jedna etykieta: {single} | Wiele etykiet: {len(kept) - single}")
    for label, count in counts.most_common():
        print(f"{count:6d}  {label}")


if __name__ == "__main__":
    main()
