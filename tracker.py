import asyncio
import csv
import os
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from playwright.async_api import async_playwright

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.freetour.com/paris"
PROVIDER_KEYWORD = "discover walks"
TARGET_TOURS = [
    "Le Marais Free Tour: Where Parisians Go",
    "Paris Icons Express Tour - Notre-Dame to Louvre. Small group",
    "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur",
    "Paris Left Bank: Writers, Revolution & Black Coffee",
]

RANKINGS_FILE = Path(__file__).parent / "rankings.csv"
CHART_FILE = Path(__file__).parent / "chart.png"

PARIS_LAT = 48.8566
PARIS_LON = 2.3522

SHORT_NAMES = {
    "Le Marais Free Tour: Where Parisians Go": "Le Marais",
    "Paris Icons Express Tour - Notre-Dame to Louvre. Small group": "Paris Icons",
    "Montmartre Paris Free Tour: Moulin Rouge to Sacre Coeur": "Montmartre",
    "Paris Left Bank: Writers, Revolution & Black Coffee": "Left Bank",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def match_tour(title: str) -> Optional[str]:
    title_n = normalize(title)
    for t in TARGET_TOURS:
        if normalize(t) in title_n or title_n in normalize(t):
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

        print(f"Loading {BASE_URL} …")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(1_500)

        # --- Dismiss GDPR cookie banner if present ---
        try:
            gdpr_btn = page.locator("#gdpr button").first
            if await gdpr_btn.count() > 0:
                await gdpr_btn.wait_for(state="visible", timeout=3_000)
                await gdpr_btn.click()
                await page.wait_for_timeout(800)
                print("  Dismissed GDPR banner.")
        except Exception:
            pass

        # --- Wait for filter panel to finish its initial load ---
        try:
            await page.wait_for_selector(
                ".js-city-filters:not(.filters-preload)", timeout=15_000
            )
        except Exception:
            pass
        await page.wait_for_timeout(500)

        # --- Apply "Tour Language → English" filter ---
        print("Applying filter: Tour Language → English …")
        lang_label = page.locator('label[for="lang-english"]').first
        await lang_label.wait_for(state="visible", timeout=15_000)
        await lang_label.click(force=True)
        try:
            await page.wait_for_selector(
                ".js-city-filters:not(.filters-preload)", timeout=15_000
            )
        except Exception:
            pass
        await page.wait_for_timeout(1_000)

        # --- Apply "Category → Walking Tour" filter ---
        print("Applying filter: Category → Walking Tour …")
        type_label = page.locator('label[for="type-Walking-Tour"]').first
        await type_label.wait_for(state="visible", timeout=15_000)
        await type_label.click(force=True)
        try:
            await page.wait_for_selector(
                ".js-city-filters:not(.filters-preload)", timeout=15_000
            )
        except Exception:
            pass
        await page.wait_for_timeout(1_000)

        # --- Load ALL results by clicking "Show more activities" ---
        load_round = 0
        while True:
            show_more = page.locator(".filters-button__container .filters-button").first
            if await show_more.count() == 0 or not await show_more.is_visible():
                break
            load_round += 1
            print(f"  Loading more results (page {load_round + 1}) …")
            try:
                await show_more.scroll_into_view_if_needed()
                await show_more.click(force=True)
                await page.wait_for_load_state("networkidle", timeout=20_000)
                await page.wait_for_timeout(1_000)
            except Exception as e:
                print(f"  Show more button detached or unavailable; all results loaded.")
                break

        # --- Collect all tour cards ---
        cards = await page.query_selector_all(".city-tour.js-city-tour")
        print(f"  Total listings found: {len(cards)}")

        for idx, card in enumerate(cards, start=1):
            title_el = await card.query_selector(".city-tour__title")
            provider_el = await card.query_selector(".city-tour__provider-name")

            title_text = (await title_el.inner_text()).strip() if title_el else ""
            provider_text = (await provider_el.inner_text()).strip() if provider_el else ""

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
            writer.writerow([today, "freetour", tour, pos if pos is not None else ""])

    print(f"\nResults saved to {RANKINGS_FILE}")


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def generate_chart() -> None:
    if not RANKINGS_FILE.exists():
        print("No data to chart yet.")
        return

    df = pd.read_csv(RANKINGS_FILE, parse_dates=["date"])
    df = df.dropna(subset=["position"])
    df["position"] = df["position"].astype(int)
    if "source" in df.columns:
        df = df[df["source"] == "freetour"]

    if df.empty:
        print("No valid position data to chart.")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    colors = ["#E63946", "#457B9D", "#2A9D8F", "#E9C46A"]

    for i, tour in enumerate(TARGET_TOURS):
        tour_df = df[df["tour"] == tour].sort_values("date")
        if tour_df.empty:
            continue
        ax.plot(
            tour_df["date"],
            tour_df["position"],
            marker="o",
            label=SHORT_NAMES.get(tour, tour),
            color=colors[i % len(colors)],
            linewidth=2,
            markersize=6,
        )

    ax.invert_yaxis()  # Position 1 at the top
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    ax.set_title(
        "Discover Walks — Tour Rankings on Freetour.com/paris",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Position (lower = better)")
    ax.legend(loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.5)

    fig.tight_layout()
    fig.savefig(CHART_FILE, dpi=150)
    print(f"Chart saved to {CHART_FILE}")


# ---------------------------------------------------------------------------
# Git push
# ---------------------------------------------------------------------------

def git_push() -> None:
    repo = Path(__file__).parent
    today = date.today().isoformat()

    def run(cmd: list) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, cwd=repo, capture_output=True, text=True)

    # Check if a remote is configured; skip silently if not
    remote = run(["git", "remote", "get-url", "origin"])
    if remote.returncode != 0:
        print("\nNo git remote configured — skipping push. See DEPLOY.md to connect GitHub.")
        return

    print("\nPushing to GitHub …")
    run(["git", "add", "rankings.csv", "chart.png"])

    status = run(["git", "status", "--porcelain"])
    if not status.stdout.strip():
        print("  Nothing new to commit.")
        return

    commit = run(["git", "commit", "-m", f"rankings: {today}"])
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
    print("Freetour.com/paris — Discover Walks Position Tracker")
    print("=" * 60)

    results = await scrape_positions()

    print("\n--- Summary ---")
    for tour, pos in results.items():
        label = SHORT_NAMES.get(tour, tour)
        if pos is not None:
            print(f"  #{pos:>3}  {label}")
        else:
            print(f"  N/A   {label}  (not found on page)")

    save_to_csv(results)
    generate_chart()

    git_push()

    if os.getenv("DEBUG"):
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await (await browser.new_context()).new_page()
            await page.goto(BASE_URL)
            await page.screenshot(
                path=str(Path(__file__).parent / "debug.png"), full_page=True
            )
            await browser.close()
        print("Debug screenshot saved to debug.png")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
