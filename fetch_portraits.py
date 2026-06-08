"""
Fetch up to 3 portrait URLs per poet.
Strategy:
  1. Keep existing portraits already in portraits.json
  2. For poets with < 3: search Wikimedia Commons category for their name
  3. Fall back to Wikipedia article images

Run to refresh/extend portraits.json.
"""
import json, time
import requests
from pathlib import Path

HEADERS = {"User-Agent": "silver-age-game/1.0 (educational project)"}
OUT = Path("D:/jupyters/silver_age/static/portraits.json")

WIKI = {
    "blok":             ("Alexander_Blok",              "Alexander Blok"),
    "belyy":            ("Andrei_Bely",                 "Andrei Bely"),
    "briusov":          ("Valery_Bryusov",              "Valery Bryusov"),
    "balmont":          ("Konstantin_Balmont",          "Konstantin Balmont"),
    "sologub":          ("Fyodor_Sologub",              "Fyodor Sologub"),
    "gippiusz":         ("Zinaida_Gippius",             "Zinaida Gippius"),
    "ivanovviacheslav": ("Vyacheslav_Ivanov_(poet)",    "Vyacheslav Ivanov"),
    "annenskiy":        ("Innokenty_Annensky",          "Innokenty Annensky"),
    "voloshin":         ("Maximilian_Voloshin",         "Maximilian Voloshin"),
    "gumilev":          ("Nikolay_Gumilev",             "Nikolai Gumilev"),
    "ahmatova":         ("Anna_Akhmatova",              "Anna Akhmatova"),
    "mandelshtam":      ("Osip_Mandelstam",             "Osip Mandelstam"),
    "kuzmin":           ("Mikhail_Kuzmin",              "Mikhail Kuzmin"),
    "mayakovskiy":      ("Vladimir_Mayakovsky",         "Vladimir Mayakovsky"),
    "hlebnikov":        ("Velimir_Khlebnikov",          "Velimir Khlebnikov"),
    "severianin":       ("Igor_Severyanin",             "Igor Severyanin"),
    "hodasevich":       ("Vladislav_Khodasevich",       "Vladislav Khodasevich"),
    "cvetaeva":         ("Marina_Tsvetaeva",            "Marina Tsvetaeva"),
    "pasternak":        ("Boris_Pasternak",             "Boris Pasternak"),
    "esenin":           ("Sergei_Yesenin",              "Sergei Yesenin"),
    "kluev":            ("Nikolai_Klyuev",              "Nikolai Klyuev"),
    "ivanovg":          ("Georgy_Ivanov",               "Georgy Ivanov"),
}

SKIP_EXTS  = {".svg", ".gif", ".ogg", ".ogv", ".webm", ".pdf", ".mid", ".mp3"}
SKIP_WORDS = {
    "flag", "icon", "logo", "map", "signature", "coat", "seal",
    "grave", "tomb", "monument", "building", "street", "museum",
    "award", "medal", "wikisource", "commons-logo", "question",
    "audio", "edit", "arrow", "bullet", "book", "cover",
}


def safe_get(url, params=None):
    for _ in range(4):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=12)
            if r.status_code == 200 and r.text.strip():
                return r.json()
        except Exception:
            pass
        time.sleep(1.5)
    return {}


def file_url(filename: str, width: int = 400, api: str = "en") -> str:
    base = f"https://{api}.wikipedia.org/w/api.php" if api == "en" else \
           "https://commons.wikimedia.org/w/api.php"
    data = safe_get(base, {
        "action": "query", "titles": f"File:{filename}",
        "prop": "imageinfo", "iiprop": "url|size",
        "iiurlwidth": str(width), "format": "json",
    })
    for page in data.get("query", {}).get("pages", {}).values():
        for ii in page.get("imageinfo", []):
            if ii.get("width", 999) < 80 or ii.get("height", 999) < 80:
                continue
            url = ii.get("thumburl") or ii.get("url", "")
            if url:
                return url
    return ""


def page_image_files(article: str) -> list[str]:
    data = safe_get("https://en.wikipedia.org/w/api.php", {
        "action": "query", "titles": article,
        "prop": "images", "imlimit": "50", "format": "json",
    })
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        for img in page.get("images", []):
            name = img["title"].replace("File:", "")
            if Path(name).suffix.lower() in SKIP_EXTS:
                continue
            if any(w in name.lower() for w in SKIP_WORDS):
                continue
            results.append(name)
    return results


def commons_category_files(name: str) -> list[str]:
    """Search Wikimedia Commons for files in the person's category."""
    category = f"Category:{name}"
    data = safe_get("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "list": "categorymembers",
        "cmtitle": category, "cmtype": "file",
        "cmlimit": "30", "format": "json",
    })
    results = []
    for member in data.get("query", {}).get("categorymembers", []):
        name_ = member["title"].replace("File:", "")
        if Path(name_).suffix.lower() in SKIP_EXTS:
            continue
        if any(w in name_.lower() for w in SKIP_WORDS):
            continue
        results.append(name_)
    return results


def commons_search_files(query: str) -> list[str]:
    """Text-search Wikimedia Commons for files matching the query."""
    data = safe_get("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "list": "search",
        "srsearch": query, "srnamespace": "6",
        "srlimit": "20", "format": "json",
    })
    results = []
    for item in data.get("query", {}).get("search", []):
        name = item["title"].replace("File:", "")
        if Path(name).suffix.lower() in SKIP_EXTS:
            continue
        if any(w in name.lower() for w in SKIP_WORDS):
            continue
        results.append(name)
    return results


def collect_urls(files: list[str], existing_set: set, needed: int,
                 api: str = "commons") -> list[str]:
    found = []
    for fname in files:
        if len(found) >= needed:
            break
        url = file_url(fname, api=api)
        time.sleep(0.25)
        if url and url not in existing_set:
            found.append(url)
            existing_set.add(url)
    return found


def main():
    current: dict[str, list[str]] = {}
    if OUT.exists():
        current = json.loads(OUT.read_text("utf-8"))

    results: dict[str, list[str]] = {}

    for slug, (article, commons_name) in WIKI.items():
        existing = current.get(slug, [])
        existing_set = set(existing)
        needed = 3 - len(existing)

        if needed <= 0:
            results[slug] = existing[:3]
            print(f"{slug}: already has 3, skipping")
            continue

        new_urls = list(existing)

        # 1. Try Wikipedia article images
        if needed > 0:
            files = page_image_files(article)
            time.sleep(0.4)
            found = collect_urls(files, existing_set, needed, api="en")
            new_urls.extend(found)
            needed -= len(found)

        # 2. Try Commons category
        if needed > 0:
            files = commons_category_files(commons_name)
            time.sleep(0.4)
            found = collect_urls(files, existing_set, needed, api="commons")
            new_urls.extend(found)
            needed -= len(found)

        # 3. Try Commons text search
        if needed > 0:
            files = commons_search_files(commons_name)
            time.sleep(0.4)
            found = collect_urls(files, existing_set, needed, api="commons")
            new_urls.extend(found)
            needed -= len(found)

        results[slug] = new_urls[:3]
        added = len(new_urls) - len(existing)
        print(f"{slug}: {len(existing)} -> {len(new_urls[:3])} (+{added})")

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in results.values())
    have3 = sum(1 for v in results.values() if len(v) >= 3)
    print(f"\nTotal portraits: {total}  |  poets with 3: {have3}/{len(results)}")


if __name__ == "__main__":
    main()
