import asyncio
import csv
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GURUWALK_URL = (
    "https://www.guruwalk.com/a/search?vertical=free-tour&hub=paris&langs=en"
)
PROVIDER_KEYWORD = "charing cross"
TARGET_TOURS = [
    "Paris Old Town - small group - Notre Dame and Latin Quarter",
    "Le Marais without the crowds, the beating heart of Paris",
    "Paris starts here - the tour for first timers. Small Group",
    "The village of Montmartre without the crowds",
    "Seeing Paris - the most visual tour of Paris. Small group",
    "Small-Group free tour: Secret Paris - the hidden gems tourists never see",
    "Saint Germain and Latin Quarter in a small group",
]

SHORT_NAMES = {
    "Paris Old Town - small group - Notre Dame and Latin Quarter": "Old Town",
    "Le Marais without the crowds, the beating heart of Paris": "Le Marais",
    "Paris starts here - the tour for first timers. Small Group": "First Timers",
    "The village of Montmartre without the crowds": "Montmartre",
    "Seeing Paris - the most visual tour of Paris. Small group": "Seeing Paris",
    "Small-Group free tour: Secret Paris - the hidden gems tourists never see": "Secret Paris",
    "Saint Germain and Latin Quarter in a small group": "Saint Germain",
}

RANKINGS_FILE = Path(__file__).parent / "rankings.csv"

PARIS_LAT = 48.8566
PARIS_LON = 2.3522

# Typographic quote code points: left/right single (U+2018/9), left/right double (U+201C/D)
_CURLY_QUOTES = "".join([chr(0x2018), chr(0x2019), chr(0x201C), chr(0x201D)])
_QUOTE_STRIP = re.compile("[" + re.escape(_CURLY_QUOTES) + "\"']")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    text = _QUOTE_STRIP.sub("", text.lower())
    return " ".join(text.split())


def match_tour(title: str) -> Optional[str]:
    title_n = normalize(title)
    for t in TARGET_TOURS:
        t_n = normalize(t)
        if t_n in title_n or title_n in t_n:
            return t
    return None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

async def scrape_positions() -> dict:
    results: dict = {t: None for t in TARGET_TOURS}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            geolocation={"latitude": PARIS_LAT, "longitude": PARIS_LON},
            permissions=["geolocation"],
            locale="fr-FR",
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8"},
        )
        page = await context.new_page()

        print(f"Loading {GURUWALK_URL} ...")
        await page.goto(GURUWALK_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(4_000)

        # --- Load all results via "Load more" button ---
        load_round = 0
        while True:
            btn = page.locator("button:has-text(\"Load more\")").first
            if await btn.count() == 0 or not await btn.is_visible():
                break
            load_round += 1
            prev_count = await page.evaluate(
                "() => document.querySelectorAll('[class*=\"group/card\"]').length"
            )
            await btn.scroll_into_view_if_needed()
            await btn.click()
            for _ in range(8):
                await page.wait_for_timeout(1_000)
                new_count = await page.evaluate(
                    "() => document.querySelectorAll('[class*=\"group/card\"]').length"
                )
                if new_count > prev_count:
                    break
            print(f"  Loading more results (round {load_round}): {new_count} cards")
            if new_count == prev_count:
                break

        # --- Collect all tour cards ---
        cards = await page.query_selector_all("[class*='group/card']")
        print(f"  Total listings found: {len(cards)}")

        for idx, card in enumerate(cards, start=1):
            title_el = await card.query_selector(".line-clamp-2")
            provider_el = await card.query_selector(".line-clamp-1")

            title_text = (await title_el.inner_text()).strip() if title_el else ""
            provider_text = (await provider_el.inner_text()).strip() if provider_el else ""

            if PROVIDER_KEYWORD not in provider_text.lower():
                continue

            matched = match_tour(title_text)
            if matched and results[matched] is None:
                results[matched] = idx
                print(f"    [#{idx}] FOUND: {matched}")

        await browser.close()

    return results


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def save_to_csv(results: dict) -> None:
    today = date.today().isoformat()
    file_exists = RANKINGS_FILE.exists()

    with open(RANKINGS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["date", "source", "tour", "position"])
        for tour, pos in results.items():
            writer.writerow([today, "guruwalk", tour, pos if pos is not None else ""])

    print(f"\nResults saved to {RANKINGS_FILE}")


# ---------------------------------------------------------------------------
# Git push
# ---------------------------------------------------------------------------

def git_push() -> None:
    if os.getenv("CI"):
        print("\nRunning in CI -- git push handled by workflow.")
        return

    repo = Path(__file__).parent
    today = date.today().isoformat()

    def run(cmd: list) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)

    remote = run(["git", "remote", "get-url", "origin"])
    if remote.returncode != 0:
        print("\nNo git remote configured -- skipping push.")
        return

    print("\nPushing to GitHub ...")
    run(["git", "add", "rankings.csv"])

    status = run(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("  Nothing new to commit.")
        return

    commit = run(["git", "commit", "-m", f"guruwalk rankings: {today}"])
    if commit.returncode != 0:
        print(f"  Commit failed: {commit.stderr.strip()}")
        return

    push = run(["git", "push", "origin", "main"])
    if push.returncode == 0:
        print("  Pushed successfully.")
    else:
        print(f"  Push failed: {push.stderr.strip()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 60)
    print("GuruWalk/paris -- Charing Cross Position Tracker")
    print("=" * 60)

    results = await scrape_positions()

    print("\n--- Summary ---")
    for tour, pos in results.items():
        label = SHORT_NAMES.get(tour, tour)
        if pos is not None:
            print(f"  #{pos:>3}  {label}")
        else:
            print(f"  N/A   {label}  (not listed today)")

    save_to_csv(results)
    git_push()

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
