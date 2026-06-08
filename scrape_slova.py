"""
Scrape Silver Age poems from slova.org.ru into poems.db.
Run: python scrape_slova.py
Resumes automatically if interrupted (already-scraped URLs are skipped).
"""
import re
import time
import sqlite3
import requests
from pathlib import Path
from bs4 import BeautifulSoup

DB_PATH = Path("D:/jupyters/silver_age/poems.db")
BASE = "https://slova.org.ru"
DELAY = 0.5  # seconds between requests

POETS = {
    "blok":             ("Блок",           "/blok/"),
    "belyy":            ("Белый",          "/belyy/"),
    "briusov":          ("Брюсов",         "/briusov/"),
    "balmont":          ("Бальмонт",       "/balmont/"),
    "sologub":          ("Сологуб",        "/sologub/"),
    "gippiusz":         ("Гиппиус",        "/gippiusz/"),
    "ivanovviacheslav": ("Вяч. Иванов",    "/ivanovviacheslav/"),
    "annenskiy":        ("Анненский",      "/annenskiy/"),
    "voloshin":         ("Волошин",        "/voloshin/"),
    "gumilev":          ("Гумилёв",        "/gumilev/"),
    "ahmatova":         ("Ахматова",       "/ahmatova/"),
    "mandelshtam":      ("Мандельштам",    "/mandelshtam/"),
    "kuzmin":           ("Кузмин",         "/kuzmin/"),
    "mayakovskiy":      ("Маяковский",     "/mayakovskiy/"),
    "hlebnikov":        ("Хлебников",      "/hlebnikov/"),
    "severianin":       ("Северянин",      "/severianin/"),
    "hodasevich":       ("Ходасевич",      "/hodasevich/"),
    "cvetaeva":         ("Цветаева",       "/cvetaeva/"),
    "pasternak":        ("Пастернак",      "/pasternak/"),
    "esenin":           ("Есенин",         "/esenin/"),
    "kluev":            ("Клюев",          "/kluev/"),
    "ivanovg":          ("Георгий Иванов", "/ivanovg/"),
}

YEAR_RE = re.compile(r"\b(18[5-9]\d|19[0-4]\d)\b")


def setup_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS poems (
            id          INTEGER PRIMARY KEY,
            author_slug TEXT NOT NULL,
            author_name TEXT NOT NULL,
            title       TEXT,
            year        INTEGER,
            text        TEXT NOT NULL,
            source_url  TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS games (
            id           TEXT PRIMARY KEY,
            player_name  TEXT,
            poem_ids     TEXT,
            current_turn INTEGER DEFAULT 0,
            scores       TEXT DEFAULT '[]',
            finished     INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS leaderboard (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            total_score INTEGER NOT NULL,
            finished_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def get_poem_links(session: requests.Session, author_path: str) -> list[str]:
    url = BASE + author_path
    r = session.get(url, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    seen: set[str] = set()
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only direct poem pages: /slug/poem-slug/ (exactly 3 slashes)
        if (href.startswith(author_path)
                and href != author_path
                and href.count("/") == 3
                and href not in seen):
            seen.add(href)
            links.append(href)
    return links


def scrape_poem(session: requests.Session, path: str) -> dict | None:
    r = session.get(BASE + path, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    main = soup.find("div", class_="grid-col-3")
    if not main:
        return None
    h1 = main.find("h1")
    title = h1.get_text(strip=True) if h1 else "* * *"

    # Format 1: poem text in a <pre> block
    pre = main.find("pre")
    if pre:
        em = pre.find("em")
        year = None
        if em:
            m = YEAR_RE.search(em.get_text())
            year = int(m.group()) if m else None
            em.decompose()
        text = pre.get_text().strip()
        if len(text.splitlines()) < 4:
            return None
        return {"title": title, "year": year, "text": text}

    # Format 2: each stanza in a <p> tag, lines separated by <br/>
    content_div = main.find("div")
    if not content_div:
        return None
    year = None
    stanzas: list[str] = []
    for p in content_div.find_all("p", recursive=False):
        if p.get("class"):  # skip <p class="source"> etc.
            continue
        em = p.find("em")
        # If the <p> contains only a date in <em>, extract year and skip
        if em and not p.get_text(strip=True).replace(em.get_text(strip=True), "").strip():
            m = YEAR_RE.search(em.get_text())
            if m:
                year = int(m.group())
            continue
        for br in p.find_all("br"):
            br.replace_with("\n")
        stanza = p.get_text().strip()
        if stanza:
            stanzas.append(stanza)

    text = "\n\n".join(stanzas)
    if len(text.splitlines()) < 4:
        return None
    return {"title": title, "year": year, "text": text}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    setup_db(conn)

    # Load already-scraped URLs so we can resume
    scraped: set[str] = {
        row[0] for row in conn.execute("SELECT source_url FROM poems WHERE source_url IS NOT NULL")
    }
    print(f"Already scraped: {len(scraped)} poems\n")

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; poetry-game-bot/1.0)"

    for slug, (name, path) in POETS.items():
        print(f"-- {name} ({path}) ...", end=" ", flush=True)
        try:
            links = get_poem_links(session, path)
        except Exception as e:
            print(f"ERROR fetching index: {e}")
            continue
        time.sleep(DELAY)

        new_count = 0
        skip_count = 0
        for link in links:
            if link in scraped:
                skip_count += 1
                continue
            try:
                poem = scrape_poem(session, link)
                time.sleep(DELAY)
            except Exception as e:
                print(f"\n  ERROR {link}: {e}")
                time.sleep(2)
                continue
            if poem is None:
                scraped.add(link)
                continue
            try:
                conn.execute(
                    "INSERT INTO poems (author_slug, author_name, title, year, text, source_url)"
                    " VALUES (?,?,?,?,?,?)",
                    (slug, name, poem["title"], poem["year"], poem["text"], link),
                )
                conn.commit()
                scraped.add(link)
                new_count += 1
            except sqlite3.IntegrityError:
                pass  # duplicate source_url

        total = conn.execute(
            "SELECT COUNT(*) FROM poems WHERE author_slug=?", (slug,)
        ).fetchone()[0]
        print(f"done  (+{new_count} new, {skip_count} skipped) → {total} total")

    conn.close()
    grand = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM poems").fetchone()[0]
    print(f"\nTotal poems in DB: {grand}")


if __name__ == "__main__":
    main()
