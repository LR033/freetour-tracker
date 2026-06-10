"""Run both scrapers sequentially. Called by the cron job."""
import asyncio
import sys
from pathlib import Path

# Add project root to path so imports resolve
sys.path.insert(0, str(Path(__file__).parent))

import tracker
import guruwalk_tracker


async def main() -> None:
    print("\n" + "=" * 60)
    print("RUN ALL — Freetour + GuruWalk")
    print("=" * 60 + "\n")

    # --- Freetour ---
    ft_results, ft_top3 = await tracker.scrape_positions()
    print("\n--- Freetour Summary ---")
    for tour, pos in ft_results.items():
        label = tracker.SHORT_NAMES.get(tour, tour)
        print(f"  {'#' + str(pos):>4}  {label}" if pos else f"  N/A   {label}")
    tracker.save_to_csv(ft_results)
    tracker.save_top3_csv(ft_top3)
    tracker.generate_chart()

    # --- GuruWalk ---
    gw_results, gw_top3 = await guruwalk_tracker.scrape_positions()
    print("\n--- GuruWalk Summary ---")
    for tour, pos in gw_results.items():
        label = guruwalk_tracker.SHORT_NAMES.get(tour, tour)
        print(f"  {'#' + str(pos):>4}  {label}" if pos else f"  N/A   {label}  (not listed today)")
    guruwalk_tracker.save_to_csv(gw_results)
    guruwalk_tracker.save_top3_csv(gw_top3)

    # Single git push covering both sets of results
    tracker.git_push()

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
