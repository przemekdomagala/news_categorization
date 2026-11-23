"""Keep articles with exactly one label from the 8 groups."""

import csv
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).parent / "data" / "clean" / "articles.csv"
OUTPUT = Path(__file__).parent / "data" / "clean" / "articles_single.csv"


def main():
    with SOURCE.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        rows = [row for row in reader if "|" not in row["label"]]

    with OUTPUT.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Zapisano: {OUTPUT}")
    print(f"Jedna etykieta: {len(rows)}")
    for label, count in Counter(row["label"] for row in rows).most_common():
        print(f"{count:6d}  {label}")


if __name__ == "__main__":
    main()
