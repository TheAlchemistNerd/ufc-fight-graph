# UFC Stats Scraping & Analysis Plan

## Research Notes

### 1. Scraping Strategy (UFCStats.com)
*   **Fighter Iteration:** Use URL pattern `http://ufcstats.com/statistics/fighters?char=[a-z]&page=all`.
*   **Data Hierarchy:**
    *   **Level 1 (Fighter List):** Basic bio and record.
    *   **Level 2 (Fighter Profile):** Career averages and fight history links.
    *   **Level 3 (Fight Details):** Detailed per-round striking and grappling stats.
*   **Hybrid Approach:** Use `requests` + `BeautifulSoup` for high-speed scraping of static content. Use `Selenium` only for pages requiring session handling or complex JS interactions (though fight details can be accessed directly via URLs).

### 2. Database Design (Neo4j)
*   **Why Graph?** MMA is a relational network. Graphs allow for deep pathfinding (common opponents, transitive wins).
*   **Schema:**
    *   **Nodes:** `Fighter`, `Fight`, `Event`, `WeightClass`, `Referee`, `Location`
    *   **Relationships:** 
        * `(:Fighter)-[:FOUGHT {result, method}]->(:Fight)`
        * `(:Fight)-[:PART_OF]->(:Event)`
        * `(:Fight)-[:IN_WEIGHT_CLASS]->(:WeightClass)`
        * `(:Fight)-[:OFFICIATED_BY]->(:Referee)`
        * `(:Fight)-[:TOOK_PLACE_AT]->(:Location)`
        * `(:Fight)-[:AGAINST]->(:Fighter)` (bidirectional from both fighters)

### 3. Expanded Data Capture
*   **Fight Details:** Referee, weight class, finish details (punch type, target), fight duration
*   **Event Pages:** Location, venue, full fight card, bonus awards
*   **Fighter Profiles:** Height, weight, reach, stance, DOB, nickname, record, gym (if available)
*   **Fight Statistics:** Per-round striking, grappling, takedowns, submissions, control time

### 4. Scaling (Google Cloud)
*   **Cloud Run:** Highly scalable for concurrent scraping.
*   **Pub/Sub:** Use as a task queue to feed fighter URLs to workers.
*   **Rate Limiting:** Control `max-instances` and use random delays to mimic human behavior.

---

## Detailed Task List

### Phase 1: Environment & POC
- [x] Task 1: Document Plan & Strategy.
- [x] Task 2: Environment Setup (`requirements.txt`).
- [x] Task 3: Develop `UfcScraper` class (Hybrid Requests/Selenium).
- [x] Task 4: Scrape Leon Edwards (Personal Info, Career Stats, Fight Details).

### Phase 2: Data Engineering
- [x] Task 5: Data Normalization (Unit conversion, record parsing).
- [x] Task 6: Neo4j Schema Setup (Constraints and Indexes).
- [x] Task 7: Implementation of `Neo4jLoader`.

### Phase 3: Full Crawl
- [x] Task 8: Dockerization & Cloud Run Deployment.
- [x] Task 9: Implement Alphabetical Crawler.
- [x] Task 10: Capture Referee, Weight Class, Location, Finish Details.
- [x] Task 11: Crawl Event Pages for Location & Full Fight Cards.
- [x] Task 12: Crawl All Events to Build Event Database.
- [x] Task 13: Full Alphabetical Fighter Crawl & Neo4j Load.

### Phase 4: Analytics
- [x] Task 14: Prototype Graph Centrality Query.
- [x] Task 15: Win/Loss Network Analysis.
- [x] Task 16: Fighter Similarity Clustering.

---

## How to Run

```bash
# Full crawl (events + fighters + enriched fights)
python main.py

# Events only
python main.py --events-only

# Fighters only
python main.py --fighters-only

# Test run (5 events, fighters A-B)
python main.py --test

# Custom sample fight enrichment count
python main.py --sample-fights 50
```

The Neo4j graph at `bolt://localhost:7687` will contain the complete UFC database ready for graph analytics (centrality, pathfinding, etc.).
