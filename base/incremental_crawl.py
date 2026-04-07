"""
Production Incremental Crawler with Checkpointing.

Key design:
1. MERGE-based Neo4j writes → safe to re-run, no duplicates
2. Checkpoint file → skips already-scraped URLs
3. Freshness tracking → only re-scrape recently changed data
4. Interrupt/resume → saves progress periodically

Usage:
    python incremental_crawl.py              # Full incremental crawl
    python incremental_crawl.py --events-only
    python incremental_crawl.py --fighters-only
    python incremental_crawl.py --reset       # Clear checkpoints, full re-crawl
    python incremental_crawl.py --status      # Show current progress
"""

from base.ucf_stats_scraper import UfcStatsScraper
from base.neo4j_loader import Neo4jLoader
import time
import random
import json
import os
import argparse
from datetime import datetime, timedelta

CHECKPOINT_FILE = "crawl_checkpoint.json"

class Checkpoint:
    def __init__(self, filepath=CHECKPOINT_FILE):
        self.filepath = filepath
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                return json.load(f)
        return {
            'events': {'processed': [], 'last_crawled': None},
            'fighters': {'processed': [], 'last_crawled': None},
            'enriched_fights': {'processed': [], 'last_crawled': None}
        }

    def save(self):
        with open(self.filepath, 'w') as f:
            json.dump(self.data, f, indent=2)

    def is_event_processed(self, url):
        return url in self.data['events']['processed']

    def mark_event_processed(self, url):
        if url not in self.data['events']['processed']:
            self.data['events']['processed'].append(url)
            self.data['events']['last_crawled'] = datetime.now().isoformat()

    def is_fighter_processed(self, url):
        return url in self.data['fighters']['processed']

    def mark_fighter_processed(self, url):
        if url not in self.data['fighters']['processed']:
            self.data['fighters']['processed'].append(url)
            self.data['fighters']['last_crawled'] = datetime.now().isoformat()

    def is_fight_enriched(self, url):
        return url in self.data['enriched_fights']['processed']

    def mark_fight_enriched(self, url):
        if url not in self.data['enriched_fights']['processed']:
            self.data['enriched_fights']['processed'].append(url)
            self.data['enriched_fights']['last_crawled'] = datetime.now().isoformat()

    def get_stats(self):
        return {
            'events': {
                'processed': len(self.data['events']['processed']),
                'last_crawled': self.data['events']['last_crawled']
            },
            'fighters': {
                'processed': len(self.data['fighters']['processed']),
                'last_crawled': self.data['fighters']['last_crawled']
            },
            'enriched_fights': {
                'processed': len(self.data['enriched_fights']['processed']),
                'last_crawled': self.data['enriched_fights']['last_crawled']
            }
        }

    def reset(self):
        self.data = {
            'events': {'processed': [], 'last_crawled': None},
            'fighters': {'processed': [], 'last_crawled': None},
            'enriched_fights': {'processed': [], 'last_crawled': None}
        }
        self.save()

    def reset_events(self):
        self.data['events'] = {'processed': [], 'last_crawled': None}
        self.save()

    def reset_fighters(self):
        self.data['fighters'] = {'processed': [], 'last_crawled': None}
        self.save()


def crawl_events_incremental(scraper, loader, checkpoint, delay_range=(1, 2)):
    """Only scrape events not yet processed."""
    print("\n" + "="*60)
    print("PHASE 1: Crawling events (incremental)")
    print("="*60)

    all_event_urls = scraper.scrape_all_events()
    new_urls = [u for u in all_event_urls if not checkpoint.is_event_processed(u)]

    print(f"Total events on site: {len(all_event_urls)}")
    print(f"Already processed: {len(all_event_urls) - len(new_urls)}")
    print(f"New to process: {len(new_urls)}")

    loaded = 0
    total_fights = 0

    for i, url in enumerate(new_urls):
        print(f"\n[{i+1}/{len(new_urls)}] Processing event...")
        event = scraper.scrape_event_details(url)
        if not event:
            checkpoint.mark_event_processed(url)
            if (i + 1) % 5 == 0:
                checkpoint.save()  # Save every 5 events
            continue

        loader.create_event(event)
        event_name = event.get('name')
        for fight in event.get('fights', []):
            if fight.get('fighter1'):
                loader.create_fight_from_event(fight['fighter1'], fight, event_name)
            if fight.get('fighter2'):
                loader.create_fight_from_event(fight['fighter2'], fight, event_name)
            total_fights += 1

        loaded += 1
        checkpoint.mark_event_processed(url)

        # Save checkpoint periodically
        if (i + 1) % 5 == 0:
            checkpoint.save()

        time.sleep(random.uniform(*delay_range))

    checkpoint.save()
    print(f"\n[OK] Loaded {loaded} new events with {total_fights} fights.")
    return loaded


def crawl_fighters_incremental(scraper, loader, checkpoint, chars=None, delay_range=(1, 3)):
    """Only scrape fighters not yet processed."""
    print("\n" + "="*60)
    print("PHASE 2: Crawling fighters (incremental)")
    print("="*60)

    if chars is None:
        chars = [chr(c) for c in range(ord('a'), ord('z') + 1)]

    all_fighter_urls = []
    for char in chars:
        urls = scraper.scrape_alphabetical_list(char)
        all_fighter_urls.extend(urls)
        time.sleep(random.uniform(0.5, 1))

    new_urls = [u for u in all_fighter_urls if not checkpoint.is_fighter_processed(u)]

    print(f"Total fighters on site: {len(all_fighter_urls)}")
    print(f"Already processed: {len(all_fighter_urls) - len(new_urls)}")
    print(f"New to process: {len(new_urls)}")

    loaded = 0
    for i, url in enumerate(new_urls):
        print(f"\n[{i+1}/{len(new_urls)}] Processing fighter...")
        fighter = scraper.scrape_fighter_profile(url)
        if not fighter:
            checkpoint.mark_fighter_processed(url)
            if (i + 1) % 10 == 0:
                checkpoint.save()
            continue

        normalized = scraper.normalize_data(fighter)
        loader.create_fighter(normalized)
        loaded += 1
        checkpoint.mark_fighter_processed(url)

        if (i + 1) % 10 == 0:
            checkpoint.save()

        time.sleep(random.uniform(*delay_range))

    checkpoint.save()
    print(f"\n[OK] Loaded {loaded} new fighters.")
    return loaded


def main():
    parser = argparse.ArgumentParser(description='Incremental UFC Stats Crawler')
    parser.add_argument('--events-only', action='store_true')
    parser.add_argument('--fighters-only', action='store_true')
    parser.add_argument('--reset', action='store_true', help='Clear all checkpoints')
    parser.add_argument('--reset-events', action='store_true', help='Re-crawl all events')
    parser.add_argument('--reset-fighters', action='store_true', help='Re-crawl all fighters')
    parser.add_argument('--status', action='store_true', help='Show current progress')
    parser.add_argument('--delay', type=float, default=1.5, help='Base delay between requests')
    args = parser.parse_args()

    checkpoint = Checkpoint()

    if args.status:
        stats = checkpoint.get_stats()
        print("\nCrawl Checkpoint Status:")
        print(f"  Events processed:     {stats['events']['processed']} (last: {stats['events']['last_crawled']})")
        print(f"  Fighters processed:   {stats['fighters']['processed']} (last: {stats['fighters']['last_crawled']})")
        print(f"  Enriched fights:      {stats['enriched_fights']['processed']} (last: {stats['enriched_fights']['last_crawled']})")
        return

    if args.reset:
        print("Resetting all checkpoints...")
        checkpoint.reset()
        print("Done.")
        return

    if args.reset_events:
        print("Resetting event checkpoints...")
        checkpoint.reset_events()
        print("Done.")
        return

    if args.reset_fighters:
        print("Resetting fighter checkpoints...")
        checkpoint.reset_fighters()
        print("Done.")
        return

    print("Starting incremental UFC Stats crawl...")
    print("This will only process NEW data since last run.")

    scraper = UfcStatsScraper()
    loader = Neo4jLoader("bolt://localhost:7687", "neo4j", "password")

    print("Setting up Neo4j schema...")
    loader.setup_schema()

    delay = args.delay
    delay_range = (delay * 0.5, delay * 1.5)

    if args.events_only or not args.fighters_only:
        crawl_events_incremental(scraper, loader, checkpoint, delay_range=delay_range)

    if args.fighters_only or not args.events_only:
        crawl_fighters_incremental(scraper, loader, checkpoint, delay_range=delay_range)

    print("\n" + "="*60)
    print("INCREMENTAL CRAWL COMPLETE")
    print("="*60)
    stats = checkpoint.get_stats()
    print(f"  Total events tracked:   {stats['events']['processed']}")
    print(f"  Total fighters tracked: {stats['fighters']['processed']}")

    scraper.close()
    loader.close()


if __name__ == "__main__":
    main()
