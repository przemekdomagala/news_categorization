"""Pobiera artykuły z FreeNewsAPI z podziałem na topic do bazy SQLite.

/news zwraca tylko tytuły (10 na stronę), więc treść każdego artykułu to osobne
zapytanie do /details. Limity API: 2 zapytania/s i 5000 zapytań dziennie.
Skrypt czeka na reset limitu i można go bezpiecznie przerwać oraz wznowić.
"""

import argparse
import json
import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

API_URL = "https://api.freenewsapi.io/v1"
ENV_FILE = Path(__file__).parent / ".env"
DB_FILE = Path(__file__).parent / "data" / "news.sqlite"

# custom_search nie opisuje tematyki artykułu, więc nie nadaje się na etykietę
EXCLUDED_TOPICS = {"custom_search"}
MIN_BODY_CHARS = 200
MIN_REQUEST_INTERVAL = 0.6
MAX_BACKOFF = 300
QUOTA_RETRY_WAIT = 3600

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    uuid TEXT PRIMARY KEY,
    title TEXT,
    published_at TEXT,
    publisher TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    authors TEXT,
    topics TEXT,
    countries TEXT,
    languages TEXT,
    original_url TEXT,
    incipit TEXT,
    body TEXT
);
CREATE TABLE IF NOT EXISTS listing (
    topic TEXT NOT NULL,
    uuid TEXT NOT NULL,
    PRIMARY KEY (topic, uuid)
);
CREATE TABLE IF NOT EXISTS topic_state (
    topic TEXT PRIMARY KEY,
    cursor TEXT,
    exhausted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles (status);
CREATE INDEX IF NOT EXISTS idx_listing_uuid ON listing (uuid);
"""


def log(message):
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}", flush=True)


def read_api_key():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        name, _, value = line.partition("=")
        if name.strip() == "API_KEY":
            return value.strip().strip("\"'")
    raise SystemExit(f"Brak API_KEY w {ENV_FILE}")


def sleep_until(moment):
    # Krótkie odcinki, bo time.sleep nie odlicza czasu, gdy komputer jest uśpiony
    while (remaining := (moment - datetime.now(timezone.utc)).total_seconds()) > 0:
        time.sleep(min(remaining, 60))


class ApiClient:
    def __init__(self, api_key):
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key})
        self.last_request = 0.0
        self.requests_made = 0

    def get(self, path, params):
        """Zwraca (status, json). Ponawia przy limitach i błędach przejściowych."""
        backoff = 5
        while True:
            time.sleep(max(0.0, self.last_request + MIN_REQUEST_INTERVAL - time.monotonic()))
            self.last_request = time.monotonic()

            try:
                response = self.session.get(f"{API_URL}{path}", params=params, timeout=30)
                self.requests_made += 1
                payload = response.json()
            except (requests.RequestException, ValueError) as error:
                log(f"Błąd połączenia: {error}. Ponawiam za {backoff} s")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue

            if response.status_code == 429:
                self.handle_limit(response, payload)
                continue

            if response.status_code >= 500:
                log(f"Błąd serwera {response.status_code}. Ponawiam za {backoff} s")
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
                continue

            if response.status_code in (401, 403):
                raise SystemExit(f"Odmowa dostępu: {payload.get('error')}")

            self.wait_if_quota_used(response)
            return response.status_code, payload

    def handle_limit(self, response, payload):
        error = payload.get("error", "")
        if "quota" in error.lower():
            self.wait_for_reset(response, "Month" if "month" in error.lower() else "Day")
        else:
            time.sleep(payload.get("retry_after_ms", 1000) / 1000 + 0.1)

    def wait_if_quota_used(self, response):
        for period in ("Day", "Month"):
            if response.headers.get(f"X-RateLimit-Remaining-{period}") == "0":
                self.wait_for_reset(response, period)

    def wait_for_reset(self, response, period):
        now = datetime.now(timezone.utc)
        try:
            reset = datetime.fromisoformat(response.headers[f"X-RateLimit-Reset-{period}"])
        except (KeyError, ValueError):
            reset = now
        if reset <= now:
            reset = datetime.fromtimestamp(now.timestamp() + QUOTA_RETRY_WAIT, timezone.utc)
        log(f"Limit zużyty ({period}). Czekam do {reset.astimezone():%Y-%m-%d %H:%M:%S}")
        sleep_until(reset)
        log("Wznawiam pobieranie")


def article_topics(db, uuid, details_topics):
    listed = {row[0] for row in db.execute("SELECT topic FROM listing WHERE uuid = ?", (uuid,))}
    return listed | set(details_topics)


def load_attempts(db):
    """Liczba pobranych artykułów per topic: pozwala równoważyć klasy po wznowieniu."""
    attempts = Counter()
    query = "SELECT uuid, topics FROM articles WHERE status != 'pending'"
    for uuid, topics in db.execute(query).fetchall():
        attempts.update(article_topics(db, uuid, json.loads(topics or "[]")))
    return attempts


def fetch_page(db, client, topic):
    cursor = db.execute("SELECT cursor FROM topic_state WHERE topic = ?", (topic,)).fetchone()[0]
    params = {"topic": topic, "language": "en", "order_by": "archive"}
    if cursor:
        params["cursor"] = cursor

    status, payload = client.get("/news", params)
    if status != 200:
        log(f"Koniec listy dla '{topic}': {status} {payload.get('error')}")
        with db:
            db.execute("UPDATE topic_state SET exhausted = 1 WHERE topic = ?", (topic,))
        return

    meta = payload.get("meta", {})
    next_cursor = meta.get("next_cursor")
    exhausted = not meta.get("has_more") or not next_cursor

    with db:
        for item in payload.get("data", []):
            db.execute(
                "INSERT OR IGNORE INTO articles (uuid, title, published_at, publisher) VALUES (?, ?, ?, ?)",
                (item["uuid"], item.get("title"), item.get("published_at"), item.get("publisher")),
            )
            db.execute("INSERT OR IGNORE INTO listing (topic, uuid) VALUES (?, ?)", (topic, item["uuid"]))
        db.execute(
            "UPDATE topic_state SET cursor = ?, exhausted = ? WHERE topic = ?",
            (next_cursor, int(exhausted), topic),
        )


def next_pending(db, topic):
    row = db.execute(
        """SELECT a.uuid FROM listing l JOIN articles a ON a.uuid = l.uuid
           WHERE l.topic = ? AND a.status = 'pending' LIMIT 1""",
        (topic,),
    ).fetchone()
    return row[0] if row else None


def fetch_details(db, client, uuid):
    """Zapisuje szczegóły i zwraca listę topiców artykułu."""
    status, payload = client.get("/details", {"uuid": uuid})
    if status != 200:
        log(f"Pomijam {uuid}: {status} {payload.get('error')}")
        with db:
            db.execute("UPDATE articles SET status = 'failed' WHERE uuid = ?", (uuid,))
        return []

    data = payload["data"]
    with db:
        db.execute(
            """UPDATE articles SET status = 'done', title = ?, published_at = ?, publisher = ?,
               authors = ?, topics = ?, countries = ?, languages = ?, original_url = ?,
               incipit = ?, body = ? WHERE uuid = ?""",
            (
                data.get("title"),
                data.get("published_at"),
                data.get("publisher"),
                json.dumps(data.get("authors") or [], ensure_ascii=False),
                json.dumps(data.get("topics") or [], ensure_ascii=False),
                json.dumps(data.get("countries") or []),
                json.dumps(data.get("languages") or []),
                data.get("original_url"),
                data.get("incipit"),
                data.get("body"),
                uuid,
            ),
        )
    return data.get("topics") or []


def count_usable(db):
    query = "SELECT COUNT(*) FROM articles WHERE status = 'done' AND LENGTH(TRIM(body)) >= ?"
    return db.execute(query, (MIN_BODY_CHARS,)).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=12000, help="docelowa liczba artykułów z treścią")
    args = parser.parse_args()

    DB_FILE.parent.mkdir(exist_ok=True)
    db = sqlite3.connect(DB_FILE, timeout=60)
    db.executescript(SCHEMA)
    client = ApiClient(read_api_key())

    _, payload = client.get("/topics", {})
    topics = [topic for topic in payload["data"] if topic not in EXCLUDED_TOPICS]
    with db:
        db.executemany("INSERT OR IGNORE INTO topic_state (topic) VALUES (?)", [(t,) for t in topics])

    attempts = load_attempts(db)
    active = set(topics)
    usable = count_usable(db)
    log(f"Start: {len(topics)} topiców, gotowe artykuły: {usable}, cel: {args.target}")

    while usable < args.target and active:
        # Zawsze topic z najmniejszą liczbą artykułów, żeby klasy były jak najrówniejsze
        topic = min(active, key=lambda t: (attempts[t], t))
        uuid = next_pending(db, topic)

        if uuid is None:
            exhausted = db.execute("SELECT exhausted FROM topic_state WHERE topic = ?", (topic,)).fetchone()[0]
            if exhausted:
                log(f"Topic '{topic}' wyczerpany po {attempts[topic]} artykułach")
                active.discard(topic)
            else:
                fetch_page(db, client, topic)
            continue

        details_topics = fetch_details(db, client, uuid)
        attempts.update(article_topics(db, uuid, details_topics) | {topic})

        usable = count_usable(db)
        if client.requests_made % 100 == 0:
            log(f"Gotowe: {usable}/{args.target} | zapytania w tej sesji: {client.requests_made}")

    log(f"Koniec. Gotowe artykuły: {usable}. Zapytania w tej sesji: {client.requests_made}")


if __name__ == "__main__":
    main()
