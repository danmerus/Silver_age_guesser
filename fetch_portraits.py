"""
Fetch portrait URLs for each poet from Wikipedia REST API (summary endpoint).
Gets the main portrait. Saves to static/portraits.json as {slug: [url, ...]}.
"""
import json, time
import requests
from pathlib import Path

HEADERS = {"User-Agent": "silver-age-game/1.0 (educational project)"}
OUT = Path("D:/jupyters/silver_age/static/portraits.json")

# slug -> list of Wikipedia article names to try (for multiple portraits)
WIKI = {
    "blok":             ["Alexander_Blok"],
    "belyy":            ["Andrei_Bely"],
    "briusov":          ["Valery_Bryusov"],
    "balmont":          ["Konstantin_Balmont"],
    "sologub":          ["Fyodor_Sologub"],
    "gippiusz":         ["Zinaida_Gippius"],
    "ivanovviacheslav": ["Vyacheslav_Ivanov_(poet)"],
    "annenskiy":        ["Innokenty_Annensky"],
    "voloshin":         ["Maximilian_Voloshin"],
    "gumilev":          ["Nikolay_Gumilev"],
    "ahmatova":         ["Anna_Akhmatova"],
    "mandelshtam":      ["Osip_Mandelstam"],
    "kuzmin":           ["Mikhail_Kuzmin"],
    "mayakovskiy":      ["Vladimir_Mayakovsky"],
    "hlebnikov":        ["Velimir_Khlebnikov"],
    "severianin":       ["Igor_Severyanin"],
    "hodasevich":       ["Vladislav_Khodasevich"],
    "cvetaeva":         ["Marina_Tsvetaeva"],
    "pasternak":        ["Boris_Pasternak"],
    "esenin":           ["Sergei_Yesenin"],
    "kluev":            ["Nikolai_Klyuev"],
    "ivanovg":          ["Georgy_Ivanov"],
}


def get_summary(article: str) -> dict:
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{article}"
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code == 200 and r.text.strip():
                return r.json()
        except Exception:
            pass
        time.sleep(1.5)
    return {}


def main():
    results: dict[str, list[str]] = {}

    for slug, articles in WIKI.items():
        urls = []
        for article in articles:
            data = get_summary(article)
            thumb = data.get("thumbnail", {}).get("source", "")
            # Bump to 400px width
            if thumb:
                thumb = thumb.replace("/320px-", "/400px-")
                urls.append(thumb)
            time.sleep(0.5)

        results[slug] = urls
        print(f"{slug}: {urls[0][:70] if urls else 'NO IMAGE'}")

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    found = sum(1 for v in results.values() if v)
    print(f"\nDone. {found}/{len(results)} poets have portraits.")
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
