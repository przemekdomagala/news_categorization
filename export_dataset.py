"""Eksportuje bazę do CSV oraz JSONL per topic, usuwając duplikaty treści."""

import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from download_news import DB_FILE, EXCLUDED_TOPICS, MIN_BODY_CHARS

OUTPUT_DIR = Path(__file__).parent / "data"
CSV_FILE = OUTPUT_DIR / "articles.csv"
BY_TOPIC_DIR = OUTPUT_DIR / "by_topic"
CSV_FIELDS = ["uuid", "title", "published_at", "publisher", "original_url", "topics", "body"]


def body_hash(body):
    normalized = re.sub(r"\W+", " ", body.lower()).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def main():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row

    listed = defaultdict(set)
    for uuid, topic in db.execute("SELECT uuid, topic FROM listing"):
        listed[uuid].add(topic)

    seen_bodies = set()
    by_topic = defaultdict(list)
    skipped = Counter()
    rows = []

    query = """SELECT uuid, title, published_at, publisher, original_url, topics, body
               FROM articles WHERE status = 'done' ORDER BY published_at"""
    for row in db.execute(query):
        body = (row["body"] or "").strip()
        if len(body) < MIN_BODY_CHARS:
            skipped["za krótka treść"] += 1
            continue

        fingerprint = body_hash(body)
        if fingerprint in seen_bodies:
            skipped["duplikat treści"] += 1
            continue
        seen_bodies.add(fingerprint)

        topics = sorted((set(json.loads(row["topics"])) or listed[row["uuid"]]) - EXCLUDED_TOPICS)
        if not topics:
            skipped["brak topicu"] += 1
            continue

        article = {**dict(row), "topics": topics, "body": body}
        rows.append(article)
        for topic in topics:
            by_topic[topic].append(article)

    BY_TOPIC_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_FILE.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for article in rows:
            writer.writerow({**article, "topics": "|".join(article["topics"])})

    for topic, articles in by_topic.items():
        path = BY_TOPIC_DIR / f"{re.sub(r'[^a-z0-9]+', '_', topic.lower())}.jsonl"
        with path.open("w", encoding="utf-8") as output:
            for article in articles:
                output.write(json.dumps(article, ensure_ascii=False) + "\n")

    print(f"Artykuły: {len(rows)} | Pominięte: {dict(skipped)}")
    print(f"Artykuły z wieloma topicami: {sum(len(a['topics']) > 1 for a in rows)}")
    for topic, articles in sorted(by_topic.items(), key=lambda item: -len(item[1])):
        print(f"{len(articles):6d}  {topic}")
    print(f"Pliki: {CSV_FILE} oraz {BY_TOPIC_DIR}/")


if __name__ == "__main__":
    main()
