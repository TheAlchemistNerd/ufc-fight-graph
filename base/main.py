"""
Full UFC Stats Crawler - Crawls all fighters, fights, events, referees, locations, weight classes.
Loads everything into Neo4j.
"""

from ucf_stats_scraper import UfcStatsScraper
from neo4j_loader import Neo4jLoader
import time
import random
import argparse

def crawl_all_events(scraper, loader, delay_range=(1, 2)):
    """Phase 1: Crawl all events and load them into Neo4j."""
    print("\n" + "="*60)
    print("PHASE 1: Crawling all events")
    print("="*60)
    
    event_urls = scraper.scrape_all_events()
    print(f"Found {len(event_urls)} events.")
    
    loaded_events = 0
    all_fight_urls = set()
    total_fights = 0
    
    for i, url in enumerate(event_urls):
        print(f"\n[{i+1}/{len(event_urls)}] Processing event...")
        event = scraper.scrape_event_details(url)
        if not event:
            continue
        
        # Load event (creates Event + Location nodes)
        loader.create_event(event)
        loaded_events += 1
        
        # Load all fights from this event
        event_name = event.get('name')
        for fight in event.get('fights', []):
            if fight.get('url'):
                all_fight_urls.add(fight['url'])
            
            # Load fight relationships for both fighters
            if fight.get('fighter1'):
                loader.create_fight_from_event(fight['fighter1'], fight, event_name)
            if fight.get('fighter2'):
                loader.create_fight_from_event(fight['fighter2'], fight, event_name)
            total_fights += 1
        
        # Rate limiting
        time.sleep(random.uniform(*delay_range))
    
    print(f"\n[OK] Loaded {loaded_events} events with {total_fights} total fights ({len(all_fight_urls)} unique fight URLs).")
    return all_fight_urls

def scrape_fight_details_for_events(scraper, loader, fight_urls, sample_size=10, delay_range=(1, 2)):
    """Phase 1b: Enrich a sample of fights with full details (referee, stats)."""
    print("\n" + "="*60)
    print(f"PHASE 1b: Enriching {min(sample_size, len(fight_urls))} fights with full details")
    print("="*60)
    
    sample = list(fight_urls)[:sample_size]
    enriched = 0
    
    for i, url in enumerate(sample):
        print(f"\n[{i+1}/{len(sample)}] Enriching fight details...")
        fight = scraper.scrape_fight_details(url)
        if not fight:
            continue
        
        # Determine results for each fighter
        fighters = fight.get('fighters', [])
        if len(fighters) >= 2:
            totals = fight.get('overall_totals', [])
            f1_result = ""
            f2_result = ""
            if len(totals) >= 2:
                f1_result = "Unknown"
                f2_result = "Unknown"
            
            fight['f1_result'] = f1_result
            fight['f2_result'] = f2_result
        
        loader.create_fight(fight)
        enriched += 1
        time.sleep(random.uniform(*delay_range))
    
    print(f"\n[OK] Enriched {enriched} fights with full details.")

def crawl_all_fighters(scraper, loader, chars=None, delay_range=(1, 3)):
    """Phase 2: Crawl all fighters alphabetically and load into Neo4j."""
    print("\n" + "="*60)
    print("PHASE 2: Crawling all fighters alphabetically")
    print("="*60)
    
    if chars is None:
        chars = [chr(c) for c in range(ord('a'), ord('z') + 1)]
    
    all_fighter_urls = []
    for char in chars:
        urls = scraper.scrape_alphabetical_list(char)
        all_fighter_urls.extend(urls)
        print(f"  Found {len(urls)} fighters starting with '{char}'")
        time.sleep(random.uniform(0.5, 1))
    
    print(f"\nTotal fighters to process: {len(all_fighter_urls)}")
    
    loaded_fighters = 0
    for i, url in enumerate(all_fighter_urls):
        print(f"\n[{i+1}/{len(all_fighter_urls)}] Processing fighter...")
        fighter = scraper.scrape_fighter_profile(url)
        if not fighter:
            continue
        
        # Normalize data
        normalized = scraper.normalize_data(fighter)
        
        # Load fighter
        loader.create_fighter(normalized)
        loaded_fighters += 1
        
        # Rate limiting
        time.sleep(random.uniform(*delay_range))
    
    print(f"\n[OK] Loaded {loaded_fighters} fighters.")
    return loaded_fighters

def main():
    parser = argparse.ArgumentParser(description='Full UFC Stats Crawler')
    parser.add_argument('--events-only', action='store_true', help='Only crawl events and fights')
    parser.add_argument('--fighters-only', action='store_true', help='Only crawl fighters alphabetically')
    parser.add_argument('--sample-fights', type=int, default=20, help='Number of fights to enrich with full details')
    parser.add_argument('--test', action='store_true', help='Test run with limited data')
    args = parser.parse_args()
    
    print("Starting UFC Stats crawl...")
    
    scraper = UfcStatsScraper()
    loader = Neo4jLoader("bolt://localhost:7687", "neo4j", "password")
    
    print("Setting up Neo4j schema...")
    loader.setup_schema()
    
    if args.test:
        print("\n[TEST MODE] Limited crawl")
        # Just 5 events, 3 fight details, fighters a-b
        event_urls = scraper.scrape_all_events()[:5]
        loaded = 0
        for url in event_urls:
            event = scraper.scrape_event_details(url)
            if event:
                loader.create_event(event)
                event_name = event.get('name')
                for fight in event.get('fights', []):
                    if fight.get('fighter1'):
                        loader.create_fight_from_event(fight['fighter1'], fight, event_name)
                    if fight.get('fighter2'):
                        loader.create_fight_from_event(fight['fighter2'], fight, event_name)
                loaded += 1
            time.sleep(1)
        print(f"[OK] Test: Loaded {loaded} events")
        
        # Sample fight details
        if event_urls:
            event = scraper.scrape_event_details(event_urls[0])
            if event and event.get('fights'):
                fight_url = event['fights'][0]['url']
                if fight_url:
                    fight = scraper.scrape_fight_details(fight_url)
                    if fight:
                        fight['f1_result'] = "Unknown"
                        fight['f2_result'] = "Unknown"
                        loader.create_fight(fight)
                        print(f"[OK] Test: Enriched 1 fight (Referee: {fight.get('referee')})")
        
        # Fighters a-b
        chars = ['a', 'b']
        crawl_all_fighters(scraper, loader, chars=chars, delay_range=(0.5, 1))
        
    elif args.events_only:
        fight_urls = crawl_all_events(scraper, loader, delay_range=(1, 2))
        scrape_fight_details_for_events(scraper, loader, fight_urls, sample_size=args.sample_fights)
        
    elif args.fighters_only:
        crawl_all_fighters(scraper, loader, delay_range=(1, 2))
        
    else:
        # Full crawl
        fight_urls = crawl_all_events(scraper, loader, delay_range=(1, 2))
        scrape_fight_details_for_events(scraper, loader, fight_urls, sample_size=args.sample_fights)
        crawl_all_fighters(scraper, loader, delay_range=(1, 2))
    
    print("\n" + "="*60)
    print("CRAWL COMPLETE")
    print("="*60)
    print(f"\nNeo4j now contains:")
    print(f"  - Events (with locations)")
    print(f"  - Fighters (with normalized stats)")
    print(f"  - Fights (with results, methods, weight classes)")
    print(f"  - Weight Classes")
    print(f"  - Referees (from enriched fights)")
    print(f"\nYou can now run graph analytics queries!")
    
    scraper.close()
    loader.close()

if __name__ == "__main__":
    main()
