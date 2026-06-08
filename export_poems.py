"""
Export poems from DB to one .txt file per author.
Also prints stats table.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("D:/jupyters/silver_age/poems.db")
OUT_DIR = Path("D:/jupyters/silver_age/poems_by_author")
OUT_DIR.mkdir(exist_ok=True)

YEAR_MIN, YEAR_MAX = 1880, 1940

SLUG_TO_FILE = {
    "blok":             "блок.txt",
    "belyy":            "белый.txt",
    "briusov":          "брюсов.txt",
    "balmont":          "бальмонт.txt",
    "sologub":          "сологуб.txt",
    "gippiusz":         "гиппиус.txt",
    "ivanovviacheslav": "иванов_вяч.txt",
    "annenskiy":        "анненский.txt",
    "voloshin":         "волошин.txt",
    "gumilev":          "гумилёв.txt",
    "ahmatova":         "ахматова.txt",
    "mandelshtam":      "мандельштам.txt",
    "kuzmin":           "кузмин.txt",
    "mayakovskiy":      "маяковский.txt",
    "hlebnikov":        "хлебников.txt",
    "severianin":       "северянин.txt",
    "hodasevich":       "ходасевич.txt",
    "cvetaeva":         "цветаева.txt",
    "pasternak":        "пастернак.txt",
    "esenin":           "есенин.txt",
    "kluev":            "клюев.txt",
    "ivanovg":          "иванов_г.txt",
}

SEP = "\n" + "=" * 60 + "\n"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    stats = conn.execute("""
        SELECT author_slug, author_name, COUNT(*) as n
        FROM poems
        WHERE year BETWEEN ? AND ?
        GROUP BY author_slug, author_name
        ORDER BY n DESC
    """, (YEAR_MIN, YEAR_MAX)).fetchall()

    print(f"{'Автор':<24} {'Стихов':>7}")
    print("-" * 33)
    for r in stats:
        print(f"{r['author_name']:<24} {r['n']:>7}")
    print("-" * 33)
    print(f"{'Итого':<24} {sum(r['n'] for r in stats):>7}")
    print()

    for r in stats:
        slug = r["author_slug"]
        name = r["author_name"]
        filename = SLUG_TO_FILE.get(slug, slug + ".txt")
        out_path = OUT_DIR / filename

        poems = conn.execute("""
            SELECT title, year, text
            FROM poems
            WHERE author_slug = ? AND year BETWEEN ? AND ?
            ORDER BY year, id
        """, (slug, YEAR_MIN, YEAR_MAX)).fetchall()

        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"{name} — стихотворения ({YEAR_MIN}–{YEAR_MAX})\n")
            f.write("=" * 60 + "\n")
            for p in poems:
                title = p["title"] or "* * *"
                f.write(f"\n[{p['year']}] {title}\n\n")
                f.write(p["text"].strip())
                f.write("\n" + SEP)

        print(f"  Написано: {out_path.name}  ({len(poems)} стихов)")

    conn.close()


if __name__ == "__main__":
    main()
