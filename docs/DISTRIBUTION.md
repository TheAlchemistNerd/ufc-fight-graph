# UFC Knowledge Graph — Distribution, Cloud Deployment & Analytics Strategy

## Part 1: Distribution Strategy

The goal is to get this project visible to three audiences: **UFC/industry decision-makers**, **the MMA community**, and **the tech/data science community**. Each requires a different angle and channel.

---

### A. UFC Management & Industry Decision-Makers

These are people who control UFC's data, analytics budgets, and broadcasting decisions. They care about **insights they don't already have** — not the scraper itself, but what it reveals.

| Channel | What to Post | Actionable Steps |
|---------|-------------|------------------|
| **1. X/Twitter** (highest UFC reach) | Thread of 3-4 visual screenshots: interesting Cypher results, referee patterns, fighter networks | Tag @arielhelwani, @BrettOkr, @MMAFighting, @danawhite, @Seansherb. Use #UFC #MMA #SportsAnalytics. Post at peak hours (9-11am ET). Lead with a hook: "I mapped every UFC fighter as a graph and found something about referee finish rates that UFC hasn't published." |
| **2. LinkedIn** | Architecture diagram + methodology article + what the graph reveals about fighter performance | Tag #SportsAnalytics #UFC #GraphDatabase #Neo4j. Search for and tag UFC employees in data/engineering roles. UFC's VP of Stats/Analytics, broadcasting partners (ESPN+), and sports betting companies all have LinkedIn presences. |
| **3. Direct Email Outreach** | One-page PDF: "What a UFC Knowledge Graph Reveals" — methodology, schema, 3 unique findings | Research UFC's stats/analytic contacts. Find the VP of Stats & Insights, broadcasting analytics teams (ESPN, BT Sport), and athletic commission data leads. A polished one-pager with real findings gets forwarded faster than code. |
| **4. UFC Stats Community** (direct outreach) | Share findings with MMA statisticians and data journalists | Contact @MMA_Research, @UFCStatsBot creators, and MMA statistical analysis accounts. Many already have partial datasets — your graph approach is the differentiator. |

**Key Insight:** UFC management responds to **data they haven't seen**, not tools. Lead with findings: referee bias, judging patterns, hidden fighter connections.

---

### B. MMA Community (Maximum Visibility)

This is where your project goes viral. The MMA community is highly engaged and loves data-driven content.

| Channel | What to Post | Actionable Steps |
|---------|-------------|------------------|
| **5. Reddit — r/MMA** (3.5M subs) | "I scraped all UFC stats and built a knowledge graph — here's what it reveals" | Lead with a **specific finding**, not "I built a scraper." Example: "I found the complete network of common opponents between champions" or "Here's every fighter who beat someone who beat Leon Edwards." Include a visual graph. Post on weekend mornings (Sat/Sun 8-10am ET). Expect AMA questions — engage. |
| **6. Reddit — r/ufc** (1M subs) | Event-specific analysis or fighter network visualization | Focus on current/recent events. After UFC pay-per-views, post: "Here's the complete graph of this event's fighters and their connections." Timing around events = massive engagement. |
| **7. Reddit — r/dataisbeautiful** (15M+ subs) | Beautiful network graph visualization of UFC fighter connections | Export your Neo4j graph to Gephi or Cytoscape. Create a force-directed layout with color-coded weight classes. Title: "Network of 5,000+ UFC Fighters — edges represent shared opponents." These posts regularly hit Reddit's front page. |
| **8. Reddit — r/neo4j** (20K subs) | Technical post: "Building a sports knowledge graph with Neo4j" | Share your Cypher queries, schema design, and Neo4j Browser screenshots. This audience appreciates the engineering challenge. |

---

### C. Tech & Data Science Community (Technical Credibility)

| Channel | What to Post | Actionable Steps |
|---------|-------------|------------------|
| **9. Kaggle** — Dataset | Export Neo4j data as CSV (fighters, fights, events). Upload as "UFC Complete Statistics Dataset" | UFC data is rarely available in structured, relational form. Include a sample Jupyter notebook with basic analysis. Tag #MMA #UFC #Sports. This drives backlinks to your GitHub. |
| **10. Kaggle** — Notebook | Create an analysis notebook using your exported data | Show fighter clustering, win prediction, or network analysis. Kaggle notebooks get upvoted and shared within the data science community. |
| **11. Medium / Substack** | Full article: "Building a UFC Knowledge Graph with Neo4j — From Scraping to Graph Analytics" | Cover: scraping strategy (hybrid requests/Selenium), data normalization, Neo4j schema design, incremental crawling, and analytics queries. Link to GitHub + Kaggle. Post to publications like @towardsdatascience, @better-programming. |
| **12. Hacker News** | Submit your GitHub repository | HN loves: web scraping + graph databases + sports. Post as "Show HN: UFC Knowledge Graph — 5,000 fighters, 10,000 fights, Neo4j." Include a link to a live demo or visualization. Best posting time: 7-9am PT weekdays. |
| **13. YouTube** | 5-minute screen recording walking through the Neo4j browser with your queries | Show the graph visually expanding as you run queries. Visual graphs perform extremely well. Title: "I Built a UFC Knowledge Graph in Neo4j — Here's What It Revealed About Fighter Networks." Include your GitHub link in description. |
| **14. Data Science Blogs** | Guest post or cross-post your Medium article | Target: Towards Data Science, Neptune.ai (graph ML), Neo4j's own blog (they accept community contributions), PyImageSearch, Analytics Vidhya. |

---

### Recommended Posting Sequence

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Polish README + GitHub (already done) | Day 0 |
| 2 | Export sample dataset → upload to Kaggle | Day 1 |
| 3 | Write Medium/Substack article | Day 1-2 |
| 4 | Post to r/MMA with a compelling finding | Day 3 (weekend) |
| 5 | X/Twitter thread with 3-4 visual screenshots | Day 3 (same day as Reddit) |
| 6 | Submit to Hacker News | Day 4 (weekday morning) |
| 7 | LinkedIn post linking to the article | Day 4-5 |
| 8 | YouTube walkthrough video | Day 5-7 |
| 9 | Direct email outreach to UFC contacts | Day 7+ |
| 10 | Guest posts on data science blogs | Day 7-14 |

**Cross-posting tip:** Never post the same content everywhere on the same day. Spread it out over 1-2 weeks so each platform gets a "fresh" angle and you can iterate based on feedback.

---

### What Gets UFC Management's Attention

The angle that works isn't the scraper — it's **insights they don't already have**:

- **Referee bias patterns** — which refs have higher finish rates? Do some refs favor decision wins?
- **Geographic judging patterns** — do some locations favor hometown fighters in decisions?
- **Hidden common-opponent chains** between champions — transitive win/loss paths
- **Fighter similarity clusters** that match real-world scouting reports
- **Weight class migration success** — which fighters perform better when moving up/down?
- **Finish rate by round** — are there statistically significant round-specific patterns?
- **Reach/stature advantages by era** — how has fighter physical evolution changed over decades?

If you find something statistically interesting, that's what gets shared and amplified.

---

## Part 2: Google Cloud Run — Full Data Pipeline

### Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Cloud Scheduler │────>│  Cloud Run (scraper) │────>│  Neo4j AuraDB    │     │  Cloud Storage │
│  (daily cron)    │     │                      │     │  (managed Neo4j) │     │  (checkpoints) │
└─────────────────┘     └──────────────────────┘     └──────────────────┘     └────────────────┘
         │                        │                          │                        │
         │              ┌──────────────────────┐              │                        │
         └─────────────>│  Pub/Sub (task queue)│<─────────────┘                        │
                        └──────────────────────┘                                       │
                               │                                                       │
                      ┌──────────────────────┐                                        │
                      │  Cloud Run workers   │<───────────────────────────────────────┘
                      │  (parallel scraping) │
                      └──────────────────────┘
```

### Why Cloud Run?

| Feature | Benefit |
|---------|---------|
| Pay-per-use ($0.0000025 per request) | Scraping runs are short bursts — you pay only for what you use |
| Auto-scaling (up to 1,000 instances) | Parallel scraping of 1,000 fighter URLs simultaneously |
| No server management | You don't manage VMs, just deploy containers |
| Built-in HTTPS | Secure endpoints for webhooks and Pub/Sub |
| Cold starts in ~2 seconds | Acceptable for cron-triggered jobs |

### Step-by-Step Setup

#### 1. Prerequisites

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable scheduler.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

#### 2. Create Neo4j AuraDB (Managed Neo4j)

```bash
# Option A: Create AuraDB instance (recommended for production)
# Go to: https://neo4j.com/cloud/aura/
# Free tier: 1GB, enough for full UFC dataset

# Option B: Run Neo4j on Cloud SQL or Compute Engine
# More control, more management overhead
```

#### 3. Update Dockerfile for Cloud Run

Create `Dockerfile.cloudrun`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run expects HTTP server on PORT
CMD ["python", "cloud_run_server.py"]
```

Create `cloud_run_server.py`:

```python
from flask import Flask, request, jsonify
from incremental_crawl import main as incremental_main
import os

app = Flask(__name__)

@app.route('/', methods=['POST'])
def trigger_crawl():
    """Triggered by Cloud Scheduler or Pub/Sub."""
    data = request.get_json(silent=True) or {}
    
    crawl_type = data.get('type', 'full')  # 'full', 'events', 'fighters'
    neo4j_uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    neo4j_user = os.environ.get('NEO4J_USER', 'neo4j')
    neo4j_pass = os.environ.get('NEO4J_PASS', 'password')
    
    # Run incremental crawl
    try:
        if crawl_type == 'events':
            # Only new events
            pass  # call incremental_crawl events function
        elif crawl_type == 'fighters':
            # Only new fighters
            pass  # call incremental_crawl fighters function
        else:
            incremental_main()  # full crawl
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
```

Update `requirements.txt` — add `flask` and `gunicorn`:

```
requests==2.31.0
beautifulsoup4==4.12.3
selenium==4.20.0
webdriver-manager==4.0.1
pandas==2.2.2
neo4j==5.20.0
lxml==5.2.1
pytest==8.2.1
flask==3.0.0
gunicorn==21.2.0
```

#### 4. Build and Deploy

```bash
# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ufc-scraper

# Deploy to Cloud Run (no authentication needed for cron)
gcloud run deploy ufc-scraper \
  --image gcr.io/YOUR_PROJECT_ID/ufc-scraper \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars NEO4J_URI=bolt://your-aura-instance.databases.neo4j.io,NEO4J_USER=neo4j,NEO4J_PASS=your-password \
  --timeout 3600 \
  --memory 2Gi \
  --max-instances 10
```

#### 5. Set Up Cloud Scheduler (Daily Cron)

```bash
# Create Pub/Sub topic
gcloud pubsub topics create ufc-crawl-topic

# Create daily scheduler job (runs at 6am UTC daily)
gcloud scheduler jobs create pubsub ufc-daily-crawl \
  --schedule "0 6 * * *" \
  --topic ufc-crawl-topic \
  --message-body '{"type": "full"}' \
  --time-zone "UTC"

# Or weekly incremental (runs Sunday at 6am)
gcloud scheduler jobs create pubsub ufc-weekly-incremental \
  --schedule "0 6 * * 0" \
  --topic ufc-crawl-topic \
  --message-body '{"type": "incremental"}' \
  --time-zone "UTC"
```

#### 6. Store Checkpoints in Cloud Storage

```bash
# Create GCS bucket for checkpoints
gsutil mb gs://ufc-crawl-checkpoints

# Upload checkpoint file
gsutil cp crawl_checkpoint.json gs://ufc-crawl-checkpoints/

# Update incremental_crawl.py to use GCS instead of local file
# (Use google-cloud-storage library)
```

#### 7. Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| Cloud Run (1 daily crawl, 30 min, 2GB) | ~$2-5/month |
| Cloud Scheduler (2 jobs) | Free |
| Pub/Sub | Free (first 10GB/month) |
| Cloud Storage (checkpoints) | ~$0.02/month |
| Neo4j AuraDB Free Tier | Free (up to 1GB) |
| Neo4j AuraDB Pro (if needed) | ~$65/month |
| **Total** | **~$2-70/month** |

### Scaling Strategy

For a full initial crawl (5,000 fighters, 768 events):

```
Cloud Run (max-instances=50)
    ├── Worker 1: Crawls events A-M (768 events → 384 instances)
    ├── Worker 2: Crawls events N-Z
    ├── Worker 3: Crawls fighters A-C
    ├── ...
    └── Worker 50: Crawls fighters X-Z

Each worker:
    1. Pulls URLs from Pub/Sub task queue
    2. Scrapes with rate limiting (1-2s delay)
    3. Writes to Neo4j via MERGE
    4. Updates checkpoint in GCS
    5. Exits when queue empty
```

Full initial crawl time: **~30-60 minutes** with 50 parallel workers (vs. 4-6 hours sequentially).

### Daily Incremental Run

New UFC events average 2-3 per week. Daily incremental run:
- Checks for new events (0-2 new)
- Checks for new fighters (0-10 new)
- Updates existing fighter records if stats changed
- **Run time: 2-5 minutes**
- **Cost: ~$0.01/run**

---

## Part 3: Additional Analytics Insights

Expand `analytics.py` with these high-value queries that differentiate your project from basic stat tracking sites.

### A. Referee Analysis (Unique Value)

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Finish rate by referee** | Which refs have highest KO/decision ratios? | Referee assignment patterns, potential bias |
| **Decision favorability by location** | Do hometown fighters win more decisions in certain cities? | Judging integrity, geographic bias |
| **Referee stoppage timing** | Average round/time a ref stops a fight | Safety patterns, referee aggressiveness |
| **Referee-fighter history** | How often does a fighter get a specific referee? | Potential referee-fighter patterns |

```cypher
// Referee finish rate analysis
MATCH (ref:Referee)<-[:OFFICIATED_BY]-(fight)
WITH ref.name AS referee,
     count(fight) AS total_fights,
     count(CASE WHEN toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO" THEN 1 END) AS ko_finishes,
     count(CASE WHEN toUpper(fight.method) CONTAINS "SUB" THEN 1 END) AS sub_finishes,
     count(CASE WHEN toUpper(fight.method) CONTAINS "DEC" THEN 1 END) AS decisions
RETURN referee,
       total_fights,
       round(toFloat(ko_finishes) / total_fights * 100, 1) AS ko_pct,
       round(toFloat(sub_finishes) / total_fights * 100, 1) AS sub_pct,
       round(toFloat(decisions) / total_fights * 100, 1) AS decision_pct
ORDER BY ko_pct DESC
LIMIT 15
```

### B. Fighter Evolution Over Time

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Physical evolution by era** | How have fighter height/reach/weight changed across decades? | Athletic evolution, scouting trends |
| **Weight class migration success** | Win rates for fighters moving up/down weight classes | Strategic career decisions |
| **Striking evolution** | How SLpM, Str Acc trends have changed by era | Sport evolution, training science |
| **Championship tenure analysis** | Average title reign duration by weight class | Historical dominance patterns |

```cypher
// Physical evolution by decade
MATCH (f:Fighter)
WHERE f.height_inches IS NOT NULL AND f.reach_inches IS NOT NULL
WITH f,
     CASE
       WHEN toInteger(f.dob) < 1980 THEN "Pre-1980"
       WHEN toInteger(f.dob) < 1990 THEN "1980s"
       WHEN toInteger(f.dob) < 2000 THEN "1990s"
       ELSE "2000s"
     END AS era
RETURN era,
       count(f) AS fighters,
       round(avg(f.height_inches), 1) AS avg_height,
       round(avg(f.reach_inches), 1) AS avg_reach,
       round(avg(f.weight_lbs), 1) AS avg_weight
ORDER BY era
```

### C. Network-Based Insights (Graph-Specific)

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Transitive win chains** | "I beat the guy who beat the guy who beat X" | Rankings validation, style matchups |
| **Style matchup clusters** | Group fighters by striking/grappling similarity | Scouting, matchmaking |
| **Community detection** | Natural fighter groupings beyond weight classes | Hidden fighting styles, training camps |
| **Influence spread** | Which gyms/camps produce the most connected fighters? | Gym prestige, talent pipelines |

```cypher
// Community detection (Louvain-style via connected components)
MATCH (f1:Fighter)-[:FOUGHT]->(fight)<-[:FOUGHT]-(f2:Fighter)
WITH f1, f2
CALL algo.unionFind.stream(
  f1.name, f2.name,
  {graph: 'cypher', write: false}
)
YIELD nodeId, setId
RETURN algo.asNode(nodeId).name AS fighter,
       setId AS community,
       count(*) OVER (PARTITION BY setId) AS community_size
ORDER BY community_size DESC, fighter
```

### D. Predictive / Advanced Analytics

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Win probability by stats** | Logistic regression on fighter stats → win likelihood | Betting models, fight predictions |
| **Upset detection** | Fights where the statistically inferior fighter won | Cinderella stories, analysis hooks |
| **Peak performance age** | At what age do fighters peak by weight class? | Career planning, contract decisions |
| **Injury/decline signals** | Statistical drops after losses or time off | Fighter health, retirement patterns |

### E. Event & Broadcasting Insights

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Card quality scoring** | Rank events by fighter win% and ranking of participants | Card matchmaking, PPV value |
| **Geographic event ROI** | Which cities produce the most finishes/decisions? | Event location planning |
| **Bonus correlation** | Which fight types earn Performance of the Night? | Bonus allocation strategy |
| **Main event impact** | Do main events have higher finish rates? | Card structure analysis |

### Recommended Priority for Implementation

1. **Referee finish rate analysis** (unique, UFC-relevant, media-worthy)
2. **Geographic judging patterns** (potentially explosive finding)
3. **Transitive win chains** (graph-specific, visually compelling)
4. **Physical evolution by era** (trend analysis, sports science angle)
5. **Weight class migration success** (fighter strategy insights)
6. **Community detection** (network ML, advanced analytics)
7. **Predictive models** (ML pipeline, Kaggle competition material)

---

### F. Striking & Grappling Efficiency Metrics

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **SLpM vs SApM ratio** | Fighters who land significantly more than they absorb | Elite strikers, defensive specialists |
| **Takedown defense vs submission rate trade-off** | Do high-TD-def fighters get caught in submissions more? | Grappling strategy analysis |
| **Strike accuracy decay by round** | Does accuracy drop in later rounds for cardio-heavy fighters | Stamina analysis, late-round betting |
| **Takedown accuracy vs control time correlation** | Which fighters actually capitalize on takedowns? | Wrestling effectiveness, not just attempts |
| **Reach advantage exploitation** | Do fighters with longer reach actually use distance effectively? | Physical advantage quantification |

```cypher
// Striking efficiency: best strikers by SLpM/SApM ratio
MATCH (f:Fighter)
WHERE f.slpm IS NOT NULL AND f.sapm IS NOT NULL AND toFloat(f.sapm) > 0
WITH f.name AS fighter, f.nickname AS nickname,
       toFloat(f.slpm) AS slpm, toFloat(f.sapm) AS sapm,
       toFloat(f.slpm) / toFloat(f.sapm) AS strike_ratio
WHERE toFloat(f.slpm) >= 2.0  // minimum activity threshold
RETURN fighter, nickname,
       round(slpm, 2) AS slpm, round(sapm, 2) AS sapm,
       round(strike_ratio, 2) AS strike_ratio
ORDER BY strike_ratio DESC
LIMIT 20
```

```cypher
// Reach advantage quantification: does reach actually matter?
MATCH (f1:Fighter)-[r1:FOUGHT]->(fight)<-[r2:FOUGHT]-(f2:Fighter)
WHERE f1.reach_inches IS NOT NULL AND f2.reach_inches IS NOT NULL
  AND r1.result = "win" AND r1 <> r2
WITH toFloat(f1.reach_inches) - toFloat(f2.reach_inches) AS reach_diff,
       count(fight) AS fights,
       count(CASE WHEN reach_diff > 0 THEN 1 END) AS longer_reach_wins
RETURN reach_diff AS reach_advantage_inches,
       fights,
       round(toFloat(longer_reach_wins) / fights * 100, 1) AS longer_reach_win_pct
ORDER BY reach_diff
```

---

### G. Championship & Title Fight Analysis

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Title defense streak** | Longest consecutive title defense runs by champion | Historical greatness, GOAT debates |
| **Champion vs interim champion outcomes** | How often does interim champ beat real champ in unification? | Interim title legitimacy |
| **Title fight finish rate vs non-title** | Are championship fights more/less likely to end in KO/decision? | Championship pressure, 5-round dynamics |
| **Weight class title turnover rate** | Which divisions have the most/least stable champions? | Divisional depth, matchmaking patterns |
| **Comeback champion analysis** | Fighters who lost and regained the title | Resilience, legacy metrics |

```cypher
// Title fight finish rate vs regular fights
MATCH (fight)-[:PART_OF]->(e:Event)
WHERE toUpper(e.name) CONTAINS "TITLE" OR toUpper(e.name) CONTAINS "CHAMPION"
WITH count(fight) AS title_fights,
     count(CASE WHEN toUpper((fight).method) CONTAINS "KO" OR toUpper((fight).method) CONTAINS "TKO" OR toUpper((fight).method) CONTAINS "SUB" THEN 1 END) AS title_finishes
MATCH (fight2)
WITH title_fights, title_finishes,
     count(fight2) AS total_fights,
     count(CASE WHEN toUpper(fight2.method) CONTAINS "KO" OR toUpper(fight2.method) CONTAINS "TKO" OR toUpper(fight2.method) CONTAINS "SUB" THEN 1 END) AS total_finishes
RETURN round(toFloat(title_finishes) / title_fights * 100, 1) AS title_finish_pct,
       round(toFloat(total_finishes) / total_fights * 100, 1) AS overall_finish_pct,
       title_fights, total_fights
```

---

### H. Fight Pace & Card Structure Analysis

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Average fight duration by weight class** | Which divisions have the longest/shortest fights? | Card pacing, broadcast time optimization |
| **Prelim vs main card finish rate** | Are prelim fights more/less exciting than main card? | Card structure decisions, viewer retention |
| **Event duration prediction** | How long does an average X-fight card last? | Broadcast scheduling, PPV timing |
| **Shortest fights in UFC history** | Sub-60-second finishes by weight class | Viral content, knockout compilations |
| **Longest fights (5-round wars)** | Total strike count and control time for marathon fights | Fighter durability, fan engagement |

```cypher
// Average fight duration by weight class
MATCH (fight)-[:IN_WEIGHT_CLASS]->(wc:WeightClass)
WHERE fight.round IS NOT NULL AND fight.time IS NOT NULL
WITH wc.name AS weight_class, fight,
     toInteger(fight.round) AS round_num,
     split(fight.time, ":") AS time_parts,
     toInteger(time_parts[0]) * 60 + toInteger(time_parts[1]) AS time_seconds
WITH weight_class,
     (round_num - 1) * 300 + time_seconds AS fight_duration_seconds,
     fight
RETURN weight_class,
       round(avg(fight_duration_seconds), 0) AS avg_duration_sec,
       round(avg(fight_duration_seconds) / 60, 1) AS avg_duration_min,
       count(fight) AS fights
ORDER BY avg_duration_sec ASC
```

---

### I. Career Trajectory & Longevity Analysis

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Average career length** | How many years/fights does the average UFC career last? | Fighter development, retirement patterns |
| **Win streak impact on rankings** | Does a 5-fight win streak guarantee title shot? | Ranking system validation |
| **Layoff impact on performance** | How does time off affect win rates? | Injury recovery, contract decisions |
| **Age at debut vs career success** | Do younger debutants have longer/better careers? | Scouting strategy, development investment |
| **Career arc clustering** | Group fighters by career trajectory patterns | Talent identification, prospect evaluation |

```cypher
// Layoff impact: fighters with 12+ months between fights
MATCH (f:Fighter)-[r1:FOUGHT]->(fight1),
      (f)-[r2:FOUGHT]->(fight2)
WHERE fight1.date IS NOT NULL AND fight2.date IS NOT NULL
  AND fight1 <> fight2
WITH f, r1, r2, fight1, fight2,
     duration.between(
       date(coalesce(split(fight1.date, ",")[0], "2000-01-01")),
       date(coalesce(split(fight2.date, ",")[0], "2000-01-01"))
     ).months AS layoff_months
WHERE abs(layoff_months) >= 12
WITH f.name AS fighter,
       abs(layoff_months) AS layoff,
       r2.result AS result_after_layoff,
       count(fight2) AS fights_after_layoff
RETURN fighter, layoff, result_after_layoff, fights_after_layoff
ORDER BY layoff DESC
LIMIT 20
```

---

### J. Betting & Wagering Insights

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Underdog win rate by method** | Do underdogs win more by KO or decision? | Betting value analysis |
| **Favorite win streak by odds range** | How often do heavy favorites (-500+) actually win? | Upset frequency, book accuracy |
| **Method-of-victory prediction** | Can fighter stats predict KO/Sub/Decision? | Prop betting models |
| **Divisional betting efficiency** | Which weight classes are easiest/hardest to predict? | Market liquidity, line accuracy |
| **Post-loss rebound rate** | Do fighters bounce back after their first loss? | Live betting opportunities |

```cypher
// Underdog analysis: fighters with more losses than wins who still win
MATCH (f:Fighter)-[r:FOUGHT {result: "win"}]->(fight)
WHERE toInteger(f.wins) < toInteger(f.losses)
WITH f.name AS fighter, f.wins AS career_wins, f.losses AS career_losses,
       count(fight) AS upset_wins,
       collect(distinct fight.method) AS upset_methods
RETURN fighter, career_wins, career_losses, upset_wins, upset_methods
ORDER BY upset_wins DESC
LIMIT 15
```

---

### K. Style Matchup Analysis

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Striker vs grappler win rate** | Do pure strikers beat pure grapplers more often? | Style-based matchmaking, betting edges |
| **Orthodox vs southpaw success** | Does stance matter in outcomes? | Training camp preparation |
| **Counter-striker vs aggressive striker** | Which striking styles dominate others? | Technical analysis, coaching insights |
| **Pressure fighter success rate** | Do forward-moving fighters win more? | Strategy effectiveness |
| **Cage control vs octagon control** | Which control metric better predicts wins? | Judging criteria validation |

```cypher
// Stance matchup analysis
MATCH (f1:Fighter)-[r1:FOUGHT {result: "win"}]->(fight)<-[r2:FOUGHT]-(f2:Fighter)
WHERE f1.stance IS NOT NULL AND f2.stance IS NOT NULL
  AND f1.stance <> f2.stance
WITH f1.stance AS winner_stance, f2.stance AS loser_stance,
       count(fight) AS wins
RETURN winner_stance, loser_stance, wins
ORDER BY wins DESC
```

---

### L. Gym & Training Camp Analysis

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Top gyms by output volume** | Which camps produce the most UFC fighters? | Gym prestige, talent pipelines |
| **Gym win rate ranking** | Which camps have the highest fighter win percentage? | Training quality measurement |
| **Camp style signatures** | Does a gym's fighters share statistical patterns? | Coaching influence quantification |
| **Inter-gym rivalry outcomes** | Head-to-head records between top camps | Gym prestige, matchmaking storylines |

```cypher
// If gym data is available (from fighter profiles or external sources)
MATCH (f:Fighter)-[r:FOUGHT]->(fight)
WHERE f.gym IS NOT NULL
WITH f.gym AS gym,
       count(r) AS total_fights,
       count(CASE WHEN r.result = "win" THEN 1 END) AS gym_wins,
       count(DISTINCT f) AS active_fighters
WHERE total_fights >= 10
RETURN gym,
       round(toFloat(gym_wins) / total_fights * 100, 1) AS win_pct,
       gym_wins, total_fights, active_fighters
ORDER BY gym_wins DESC
LIMIT 20
```

---

### M. Media & Fan Engagement Metrics

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Most "viral" fights** | Highest total strikes + finish in close time = highlight reel gold | Social media content, PPV highlights |
| **Fighter name recognition** | Fighters with most connections in the graph = most discussed | Marketing value, merchandising |
| **Event hype correlation** | Do highly-connected fighter matchups correlate with PPV buys? | Card matchmaking, marketing spend |
| **Comeback story detection** | Fighters who lost multiple then won streak = narrative gold | Broadcasting storytelling, documentary material |

---

### N. Historical Era Comparisons

| Query | What It Reveals | UFC Relevance |
|-------|-----------------|---------------|
| **Golden era identification** | Which years had highest finish rates, most competitive fights? | Nostalgia marketing, historical context |
| **Rule change impact** | How did 5-round main events, weight class changes affect outcomes? | Regulatory impact analysis |
| **Evolution of fighting styles** | Shift from wrestling-heavy to striking-heavy eras | Sport development, training trends |
| **International expansion impact** | How did global events change fighter demographics? | Market growth measurement |

```cypher
// Finish rate by year to identify "excitement" eras
MATCH (fight)-[:PART_OF]->(e:Event)
WHERE e.date IS NOT NULL
WITH e.date AS event_date, fight,
     toInteger(split(e.date, ",")[1]) AS year
WHERE year IS NOT NULL
WITH year,
       count(fight) AS total_fights,
       count(CASE WHEN toUpper(fight.method) CONTAINS "KO" OR toUpper(fight.method) CONTAINS "TKO" OR toUpper(fight.method) CONTAINS "SUB" THEN 1 END) AS finishes
RETURN year,
       total_fights, finishes,
       round(toFloat(finishes) / total_fights * 100, 1) AS finish_pct
ORDER BY year ASC
```

---

## Summary: What Makes This Project Unique

| Competitor | What They Do | What You Do Better |
|------------|-------------|-------------------|
| UFCStats.com | Raw fight stats | **Graph relationships** — connections, paths, patterns |
| Tapology.com | Fight records, rankings | **Network analysis** — transitive wins, similarity clusters |
| MMA Fighting | News, commentary | **Data-driven journalism** — referee patterns, judging bias |
| ESPN Stats & Info | Basic analytics | **Full historical graph** — 5,000+ fighters, 10,000+ fights |
| Betting sites | Odds, predictions | **Explainable models** — graph-based win probability with paths |

Your differentiator: **This is the only public UFC knowledge graph with referee, location, and event-level network analysis.**
