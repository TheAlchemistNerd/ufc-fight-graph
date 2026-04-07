# UFC Network Analysis: Advanced Graph Theory & ML Research Guide

## Overview

This document catalogs advanced network analysis, graph neural network, and Bayesian modeling approaches for UFC fighter analysis. Organized by implementation priority with research references, mathematical foundations, implementation strategies, and open research questions.

**Primary research source**: [Network Dynamics in Mixed Martial Arts: A Complex Systems Approach to Ultimate Fighting Championship (UFC) Competition Insights](https://arxiv.org/abs/2502.07020) (arXiv, Feb 2025)

**Implemented**: Network centrality measures (Degree, Eigenvector, Betweenness, Closeness, PageRank, Density, Path Length, Robustness, Triadic Closure) in `NetworkCentralityRepo` and Dashboard Page 11.

---

## Part 1: Centrality Measures (Implemented)

### What Was Built

The `NetworkCentralityRepo` class in `data_access/repositories.py` implements 9 centrality metrics as Cypher queries, all accessible through the dashboard (Page 11: Network Centrality).

| Metric | Cypher Approach | What It Measures | UFC Significance |
|--------|---------------|------------------|------------------|
| **Degree Centrality** | `count(DISTINCT opponent)` | Unique opponents faced | Gatekeepers, veterans, network hubs |
| **Eigenvector Centrality** | Two-hop opponent quality | Influence weighted by opponent quality | Champions and top contenders |
| **Betweenness Centrality** | Bridge detection via NOT EXISTS | Fighters connecting disconnected clusters | Multi-division fighters, era-spanners |
| **Closeness Centrality** | Two-hop reach ratio | Network reach efficiency | Efficient comparison points across roster |
| **PageRank** | Quality wins x defeated network | Loss-weighted relevance flow | Cross-weight-class, cross-era rankings |
| **Network Density** | Actual/max possible matchups | Division interconnectedness | "Shark tank" vs protected divisions |
| **Path Length** | `shortestPath()` Cypher function | Degrees of separation | Shortest fight chains between any two fighters |
| **Robustness** | Indirect/direct connection ratio | Disruption impact if removed | Load-bearing fighters critical to rankings |
| **Triadic Closure** | Triangle pattern matching | Transitivity: A>B, B>C, has A fought C? | Style matchup patterns, hierarchy breakdowns |

### Research Backing

1. **Network Dynamics in MMA** (arXiv:2502.07020, Feb 2025): Complex network analysis of UFC matchmaking evolution showing degree distribution, clustering, and betweenness centrality patterns. Key finding: Modern UFC has transitioned from tightly clustered, repetitive matchups to a decentralized, strategically curated network.

2. **PageRank for MMA Rankings** (LinkedIn MMA Analytics): Treating losses as "passing" relevance to winners enables cross-weight-class and cross-era comparisons. Outperforms ELO for non-facing fighter comparisons.

3. **Centrality in Social Networks** (ScienceDirect): Standard definitions of degree, eigenvector, betweenness, and closeness centrality applied to competitive networks.

### Key Research Finding: Success vs. Centrality
> "Winners consistently maintain higher eigenvector centrality than losers. While losing fighters may remain connected (high degree), their influence within the network typically sharpens and then fades over time as they are matched with less influential opponents."
> - arXiv:2502.07020

### Commercial Appeal Finding
> "High network dispersion (fighting new, varied opponents) is positively correlated with higher Pay-Per-View sales and Google search trends, whereas excessive clustering (rematches) can reduce engagement."
> - arXiv:2502.07020

---

## Part 2: Graph Neural Networks (GNNs) for Fight Prediction

### 2.1 Graph Attention Networks (GATs) for Outcome Prediction

#### Concept

Standard machine learning models treat fights as isolated data points (Fighter X vs Fighter Y). A GAT treats fighters as **nodes in a graph** where each node has neighbors (past opponents). The attention mechanism learns to weight past opponents differently - a win over a high-centrality veteran matters more than a win over a newcomer.

#### Mathematical Foundation

For a fighter node `i` with feature vector `h_i`:

```
h_i' = sigma( sum_{j in N(i)} alpha_ij * W * h_j )

where alpha_ij = softmax_j( LeakyReLU(a^T [W*h_i || W*h_j]) )
```

The attention coefficient `alpha_ij` learns how much fighter `j`'s characteristics influence fighter `i`'s representation.

#### Architecture

```python
# Node Features (per fighter)
fighter_features = [
    wins, losses, draws, nc,                    # Record
    height_inches, weight_lbs, reach_inches,    # Physical
    slpm, str_acc, sapm, str_def,               # Striking
    td_avg, td_acc, td_def, sub_avg,            # Grappling
    age, stance_encoded,                        # Meta
    # Centrality metrics (from our analysis)
    degree_centrality, eigenvector_centrality,
    betweenness_centrality, closeness_centrality,
    pagerank_score
]

# Edge Features (per fight)
edge_features = [
    method_encoded,         # KO/TKO/Sub/Decision
    round_finished,
    fight_duration_seconds,
    is_upset,               # Based on pre-fight odds
    days_between_fights,
    weight_class_match
]

# Graph Structure
edge_index = [[fighter_A, fighter_B], [fighter_B, fighter_A], ...]  # Bidirectional
edge_attr = [fight_1_features, fight_2_features, ...]
```

#### Implementation Path

```
Step 1: Export Neo4j graph to PyTorch Geometric format
    - Extract all FOUGHT relationships as edge_index
    - Extract fighter properties as node features (x)
    - Extract fight properties as edge attributes (edge_attr)

Step 2: Build train/test split by time
    - Train on fights before 2023
    - Test on fights in 2023-2024

Step 3: Train GAT model
    - 2-3 GAT layers with 8-16 attention heads
    - Pool node representations for each pair
    - MLP classifier for win/loss prediction

Step 4: Validate against baselines
    - Logistic regression on fighter stats alone
    - Pre-fight betting odds as baseline
    - ELO ratings as baseline

Step 5: Analyze attention weights
    - Which past opponents matter most?
    - Do centrality metrics improve prediction?
```

#### Expected Performance

Based on similar sports prediction literature:
- Logistic regression on stats: ~60-65% accuracy
- Betting odds baseline: ~65-70% accuracy
- GAT with centrality features: ~68-73% accuracy (estimated)

#### Research Questions

1. **Does GAT outperform logistic regression on fighter stats alone?**
   - Hypothesis: Yes, because opponent quality matters beyond raw stats

2. **Can attention weights reveal which past opponents matter most?**
   - Hypothesis: Wins over high-centrality fighters get higher attention weights

3. **Does incorporating centrality metrics as node features improve prediction?**
   - Hypothesis: Eigenvector centrality adds signal beyond win/loss record

#### Libraries

- `torch_geometric` - Graph neural network framework
- `torch_geometric.nn.GATConv` - Graph Attention Network layer
- `networkx` - Graph export from Neo4j

#### Data Requirements

- Full 5,000+ fighter dataset with complete stats
- Complete fight history with outcomes
- Centrality metrics (already computed)
- Pre-fight betting odds (not yet scraped)

---

### 2.2 Link Prediction for PPV Matchmaking

#### Concept

Use the GNN to predict "missing edges" (fights that haven't happened yet) and estimate the PPV ceiling based on similar triangles in the graph.

#### Architecture

```
Input: Fighter A features + Fighter B features + graph context
Output: P(fight happens) and P(PPV > threshold)

Training data:
- Positive edges: Historical fights with PPV/revenue data
- Negative edges: Fighter pairs who never fought
- Edge labels: [occurred, ppv_buy_rate, revenue_estimate]
```

#### Structural Holes Theory

GATs can identify "structural holes" - gaps between two popular but unconnected clusters. Example:

```
Cluster A (Featherweight stars): McGregor, Aldo, Holloway, Ortega
Cluster B (Lightweight stars): McGregor, Khabib, Poirier, Gaethje

Structural hole: McGregor bridges these clusters.
If McGregor retires, the structural hole reopens.
Bridging it (e.g., Holloway vs Poirier) = high revenue.
```

#### Implementation

```python
from torch_geometric.nn import GATConv
from torch_geometric.utils import negative_sampling

class PPVPredictor(torch.nn.Module):
    def __init__(self, hidden_dim):
        super().__init__()
        self.conv1 = GATConv(hidden_dim, hidden_dim, heads=8)
        self.conv2 = GATConv(hidden_dim * 8, hidden_dim, heads=1)

    def forward(self, x, edge_index, edge_attr):
        x = self.conv1(x, edge_index, edge_attr)
        x = F.relu(x)
        x = self.conv2(x, edge_index)

        # For each potential matchup (i, j)
        # Predict PPV probability
        # ...
```

#### Data Needed (Not Currently Available)

- PPV buy rates (historical estimates only, UFC doesn't publish exact numbers)
- Betting lines/opening odds
- Social media engagement metrics
- Gate revenue data

---

## Part 3: Bayesian Nonparametrics for Style Discovery

### 3.1 Hierarchical Dirichlet Process (HDP)

#### Concept

Standard analysis groups fighters into rigid categories (Striker, Wrestler, Grappler). HDP assumes the **number of fighting styles is unknown** and can grow as the sport evolves (e.g., the rise of the "Calf-Kick Meta" or "Oliveira Front Kick" style).

#### Mathematical Foundation

```
G_0 ~ DP(gamma, H)          # Base distribution over styles
G_j | G_0 ~ DP(alpha, G_0)  # Each gym/division has its own distribution
theta_ij | G_j ~ G_j         # Each fighter's style
x_ij | theta_ij ~ F(theta_ij) # Fight data generated from style
```

#### UFC Application Flow

```
1. Extract in-fight micro-data:
   - Striking volume (significant strikes landed/attempted)
   - Takedown depth and success rate
   - Control time patterns
   - Submission attempt types and success
   - Strike target distribution (head/body/leg ratios)
   - Strike position distribution (distance/clinch/ground)

2. Fit HDP to discover style clusters:
   - Cluster 1: "Heavy Hands Boxer" (high head strike ratio, high KO rate)
   - Cluster 2: "Chain Wrestler" (high TD rate, high control time)
   - Cluster 3: "Calf Kick Meta" (high leg strike ratio, specific patterns)
   - Cluster 4: "Submission Jiu-Jitsu" (high sub attempt rate, from guard)
   - Cluster 5: "Pressure Striker" (high volume, forward movement)
   - ... (unknown number, discovered by model)

3. Assign style tags to fighters (probabilistic):
   - Fighter A: 60% Cluster 1, 40% Cluster 2 = "Boxer-Wrestler"
   - Fighter B: 80% Cluster 3 = "Pure Calf Kicker"

4. Use style tags as GAT node features:
   - "Cluster 3" fighters match up poorly against "Cluster 2"
   - GAT learns these style matchup interactions
```

#### Synergy with GNN

The HDP-discovered style clusters become node features in the GAT. The GAT learns that:
- A "Cluster 7" fighter matches up poorly against "Cluster 3" fighters
- "Cluster 1" vs "Cluster 1" matchups tend toward decisions
- "Cluster 4" fighters have high upset rates against "Cluster 2"

#### Implementation Path

```python
# Phase 1: Data extraction
from sklearn.mixture import BayesianGaussianMixture

# Extract micro-data from fight details
features = extract_fighter_micro_data()  # [n_fighters, n_features]

# Phase 2: HDP fitting (approximation via BGM)
hdp = BayesianGaussianMixture(
    n_components=50,  # Upper bound, HDP will use fewer
    weight_concentration_prior=0.1,  # Controls sparsity
    weight_concentration_prior_type='dirichlet_process',
)
hdp.fit(features)

# Phase 3: Style assignment
style_assignments = hdp.predict(features)  # [n_fighters]
style_probabilities = hdp.predict_proba(features)  # [n_fighters, n_components]

# Phase 4: GAT integration
fighter_features = np.hstack([
    raw_stats,
    centrality_metrics,
    style_probabilities  # New!
])
```

#### Libraries

- `bnpy` - Bayesian nonparametric Python library
- `sklearn.mixture.BayesianGaussianMixture` - HDP approximation
- `scikit-learn` - Clustering utilities

---

### 3.2 Pitman-Yor Process (PYP) for Power-Law Fighter Influence

#### Concept

The standard Dirichlet Process (base of HDP) assumes exponential cluster sizes. The **Pitman-Yor Process** allows power-law (heavy-tailed) distributions - a few superstars have exponentially more influence than average fighters.

#### Mathematical Foundation

```
PYP(discount, concentration, base_distribution)

Key property: P(new cluster) ~ (n_k - discount) / (n + concentration)
where discount in [0, 1) controls power-law exponent

When discount = 0: reduces to Dirichlet Process (exponential)
When discount > 0: power-law (heavy-tailed)
```

#### UFC Application

In the UFC fight network:
- Jon Jones, Conor McGregor, Anderson Silva have disproportionately high centrality
- Most fighters have modest connectivity
- This follows a power-law: P(centrality > x) ~ x^(-alpha)

**Impact on Betweenness Centrality**: PYP changes how we calculate betweenness for top-tier vs entry-level fighters. The power-law weighting gives superstar bridges much higher scores than linear methods.

#### Implementation

```python
from scipy.stats import powerlaw

# Fit power-law to centrality distribution
centrality_scores = get_all_eigenvector_scores()
alpha, xmin = powerlaw.fit(centrality_scores)

# PYP-weighted betweenness
def pyp_betweenness(standard_betweenness, alpha):
    """Weight betweenness by power-law exponent."""
    return standard_betweenness ** alpha
```

---

### 3.3 Indian Buffet Process (IBP) for Multi-Style Fighters

#### Concept

HDP assigns one dominant style per fighter (clustering). **IBP is a latent feature model** - a fighter can possess multiple features simultaneously.

#### Metaphor

Chinese Restaurant Process (HDP): Each fighter sits at one table (one style).
Indian Buffet Process (IBP): Each fighter samples dishes from an infinite buffet (multiple features).

#### UFC Application

A fighter isn't just a "Wrestler" or "Striker" - they possess a subset of unbounded possible features:
- Southpaw stance
- BJJ Black Belt
- High-Altitude Training
- D-1 Wrestling Background
- Muay Thai Clinch Specialist
- Calf Kick Specialist
- Ground-and-Pound Finisher
- Card Counter (wins late-round decisions)

#### Implementation

```python
# IBP discovers features from data
# Each fighter has a binary feature vector:
# [southpaw, bjj_blackbelt, high_altitude, d1_wrestling, muay_thai, ...]

# Feature discovery without pre-defining them
from sklearn.decomposition import DictionaryLearning

# Extract features from fight data
X = extract_fighter_features()  # [n_fighters, n_micro_features]

# IBP-style sparse feature learning
ibp = DictionaryLearning(
    n_components=100,  # Maximum features
    alpha=1.0,         # Sparsity control
    fit_algorithm='lars',
    transform_algorithm='omp',
    n_nonzero_coefs=5,  # Each fighter has ~5 features
)
features = ibp.fit_transform(X)
```

---

### 3.4 Distance-Dependent Chinese Restaurant Process (ddCRP)

#### Concept

Standard CRP assumes data points are exchangeable (order doesn't matter). **ddCRP introduces temporal decay** - a fighter's recent bouts are more indicative of current form than fights from 10 years ago.

#### UFC Application

```
Decay function: weight(fight_i) = exp(-lambda * days_since_fight_i)

A fighter's centrality at time T:
centrality(T) = sum over all fights of: weight(fight_i) * centrality_contribution(fight_i)
```

#### Implementation

```python
import numpy as np
from datetime import datetime

def decayed_centrality(fights, current_date, half_life_days=365):
    """Compute centrality with temporal decay."""
    lambda_param = np.log(2) / half_life_days

    decayed_scores = []
    for fight in fights:
        days_ago = (current_date - fight.date).days
        weight = np.exp(-lambda_param * days_ago)
        decayed_scores.append(weight * fight.centrality_contribution)

    return sum(decayed_scores)
```

---

### 3.5 Sticky HDP-HMM for Career States

#### Concept

HDP-Hidden Markov Model with "sticky" transitions prevents jittering between states. Captures that fighters stay in winning streaks or slumps for sequences of fights before structural shifts.

#### UFC Application

States: [Prospect -> Contender -> Champion -> Gatekeeper -> Declining -> Retired]

The "sticky" parameter ensures that once a fighter enters "Champion" state, they don't jitter to "Declining" after one loss - they need a sustained pattern change.

#### Research Question

> Can we detect the exact fight where a fighter transitions from "prime" to "declining" based on network position shifts?

---

### 3.6 Nested Dirichlet Process (nDP) for Gym Clustering

#### Concept

HDP shares clusters across groups. **nDP clusters the groups themselves** - treating gyms as groups of fighters to identify functionally identical camps.

#### UFC Application

```
Gyms as groups:
- American Top Team: Fighters A, B, C
- City Kickboxing: Fighters D, E
- Team Alpha Male: Fighters F, G, H

nDP discovers that ATT and Alpha Male produce "High-Level Wrestling" fighters
while City Kickboxing produces "Technical Striker" fighters
```

---

## Part 4: Temporal & Dynamic Graph Analysis

### 4.1 Temporal Graph Networks (TGNs)

#### Concept

Full temporal graph modeling where edges have timestamps and node features evolve over time. TGNs learn the "half-life" of a win's significance.

#### Architecture

```
Each fight edge has: (fighter_A, fighter_B, timestamp, result, method)
Fighter node features are time-dependent: x_i(t)
TGN processes events chronologically and updates node states
```

#### Implementation

```python
from torch_geometric.nn import TGNMemory

# Event stream
events = [
    (fighter_A, fighter_B, timestamp_1, result_1),
    (fighter_C, fighter_D, timestamp_2, result_2),
    ...
]

# TGN processes events in order, maintaining temporal node states
memory = TGNMemory(num_nodes, raw_msg_dim, memory_dim, time_dim)
```

---

### 4.2 Directed Acyclic Graphs (DAGs) and Flow Analysis

#### Concept

Since fights have winners and losers, the network is directed. By looking at the "flow" of wins, we can identify:

- **Sinks**: Fighters who stop the momentum of prospects (gatekeepers who beat rising stars but never reach the top)
- **Sources**: Fighters who consistently "feed" the top of rankings (journeymen whose losses build others' records)

#### Implementation

```python
import networkx as nx

# Build directed graph: winner -> loser
G = nx.DiGraph()
for fight in fights:
    G.add_edge(fight.winner, fight.loser, method=fight.method)

# Compute flow metrics
in_degree = dict(G.in_degree())    # How many fighters this fighter beat
out_degree = dict(G.out_degree())  # How many fighters beat this fighter

# Sinks: high in-degree, low out-degree (beat many, beaten by few)
sinks = [f for f in G.nodes() if in_degree[f] > out_degree[f] * 2]

# Sources: low in-degree, high out-degree (beat few, beaten by many)
sources = [f for f in G.nodes() if out_degree[f] > in_degree[f] * 2]
```

---

## Part 5: Community Detection & Graph Partitioning

### 5.1 Louvain/Leiden Algorithm

#### Concept

Detect natural communities in the fight network. Reveals how weight classes function as nearly isolated sub-graphs.

#### UFC Application

```python
import networkx as nx
import community

# Build undirected graph
G = nx.Graph()
for fight in fights:
    G.add_edge(fight.fighter_a, fight.fighter_b)

# Community detection
partition = community.best_partition(G)

# Analyze communities
communities = {}
for fighter, comm_id in partition.items():
    communities.setdefault(comm_id, []).append(fighter)

# Find bridge fighters (fighters connecting communities)
bridge_fighters = []
for fight in fights:
    if partition.get(fight.fighter_a) != partition.get(fight.fighter_b):
        bridge_fighters.append(fight)
```

#### Key Insight

Multi-division fighters (Conor McGregor, Amanda Nunes, Daniel Cormier) are the bridges between communities. These fighters are commercially valuable for cross-divisional matchmaking.

---

### 5.2 Transitivity Coefficient

#### Concept

Global measure of clustering: what fraction of "open triangles" (A-B, B-C) are "closed" (A-C)?

#### UFC Application

High transitivity = predictable hierarchies (if A beats B and B beats C, A usually beats C).
Low transitivity = "styles make fights" (upsets and stylistic matchups break transitivity).

#### Implementation

```python
transitivity = nx.transitivity(G)

# Track over time
for year in range(2010, 2026):
    year_graph = build_graph_for_year(year)
    print(f"{year}: transitivity = {nx.transitivity(year_graph):.3f}")
```

#### Research Question

> Does transitivity decrease over time (more "styles make fights" exceptions) or increase (more predictable hierarchies)?

---

## Part 6: Expanded Data Sources

| Data Source | Graph Element | Value Add | Scraping Difficulty | Where to Get |
|-------------|--------------|-----------|-------------------|--------------|
| **Shared Training Camps** | Bipartite Fighter-Gym | Style transfer detection | Medium | Tapology, Wikipedia |
| **Social Media Metrics** | Node features | PPV prediction, hype detection | Medium | Twitter/Instagram APIs |
| **Betting Odds History** | Edge attributes | Market efficiency analysis | Hard | OddsPortal, BestFightOdds |
| **PPV Buy Rates** | Edge attributes | Revenue prediction | Hard | Industry estimates only |
| **In-Fight Micro-Data** | Edge weights | Win prediction accuracy | Medium | UFCStats.com (per-round) |
| **Weigh-In Data** | Node features | Weight cut severity | Medium | UFC weigh-in reports |
| **Travel Distance** | Edge attributes | Home turf advantage | Easy | Venue coordinates |
| **Judge Assignments** | Bipartite Fighter-Judge | Judge bias detection | Medium | UFC official records |
| **Medical Suspensions** | Node features | Injury/decline signals | Hard | State athletic commissions |
| **Sponsor Affiliations** | Node features | Commercial crossover | Medium | Fighter social media |
| **Reach/Height Evolution** | Node features over time | Athletic evolution tracking | Easy | UFCStats historical |
| **Referee Assignments** | Bipartite Fighter-Referee | Referee-fighter patterns | Medium | UFC event records |

---

## Part 7: Advanced Research Questions

### 7.1 The "Hype Train" Anomaly

**Question**: Can GNNs identify when a fighter's Social Media Centrality grows faster than their Eigenvector Centrality (skill-based importance)?

**Significance**: Identifies "overvalued" fighters for betting. If hype >> skill, the market may overprice them.

**Implementation**:
```
hype_ratio = social_media_growth_rate / eigenvector_centrality_growth_rate

If hype_ratio > 2: "Hype Train" detected - fighter is overvalued by market
```

---

### 7.2 Market Inefficiency Detection

**Question**: Where does the Bayesian Posterior for a fight outcome differ most from the Implied Probability of betting odds?

**Significance**: This is the betting "edge" - where our model disagrees with the market most.

**Implementation**:
```python
# Bayesian model output
p_win_posterior = 0.65  # Our model says 65%

# Betting odds
implied_probability = 1 / decimal_odds  # e.g., 1/1.50 = 0.667

# Edge
edge = p_win_posterior - implied_probability
if abs(edge) > 0.10:
    print(f"Significant market inefficiency: {edge:.2%}")
```

---

### 7.3 Churn Prediction

**Question**: Which fighter nodes are at risk of leaving for PFL/Bellator based on their connectivity to the UFC's "inner circle" of high-revenue matchups?

**Significance**: Early warning for talent drain.

**Indicators**:
- Declining eigenvector centrality
- Fewer connections to top-10 fighters
- Decreasing PPV association
- Long layoffs with low centrality

---

### 7.4 Revenue Elasticity

**Question**: If we add an edge between two "distant" nodes (e.g., Bantamweight moving to Featherweight), what is the predicted PPV lift compared to a standard intra-divisional matchup?

**Significance**: Optimize PPV card construction.

**Hypothesis**: Structural hole bridges produce 2-3x PPV lift over average cards.

---

### 7.5 Style Bottlenecks

**Question**: Is there a specific "style node" (e.g., Sambo) that is currently a dominant sink, absorbing wins from all other style clusters?

**Significance**: Identifies dominant meta-game styles. Triggers style adaptation by other fighters.

---

### 7.6 PageRank vs ELO

**Question**: Does PageRank outperform traditional ELO ratings when ranking fighters across different eras and weight categories?

**Research Hypothesis**: Yes, because PageRank accounts for opponent quality while ELO treats all wins equally.

---

### 7.7 Community Fragility

**Question**: If a "hub" fighter (like Jon Jones) retires, which "communities" (weight classes) lose the most connectivity and commercial relevance?

**Significance**: Quantifies the impact of star retirements on the overall ecosystem.

---

## Part 8: Implementation Priority Matrix

| Priority | Feature | Effort | Impact | Dependencies | Status |
|----------|---------|--------|--------|-------------|--------|
| **P0** | Network centrality (9 metrics) | Done | High | Data loaded | DONE |
| **P0** | Dashboard Page 11 | Done | High | Centrality data | DONE |
| **P1** | NetworkX export for visualization | 2h | High | None | TODO |
| **P1** | Community detection (Louvain) | 4h | High | Full dataset | TODO |
| **P1** | DAG flow analysis (sinks/sources) | 4h | High | Win/loss data | TODO |
| **P1** | Transitivity coefficient over time | 2h | Medium | Full dataset | TODO |
| **P2** | GAT fight outcome prediction | 20h | Very High | Complete data + odds | TODO |
| **P2** | HDP style discovery | 15h | High | In-fight micro-data | TODO |
| **P2** | Temporal decay centrality | 6h | Medium | Time-stamped data | TODO |
| **P3** | Bayesian GNN (uncertainty) | 30h | Very High | P2 complete | TODO |
| **P3** | PPV revenue prediction | 25h | High | Revenue data needed | TODO |
| **P3** | Gym bipartite graph | 8h | Medium | Gym data needed | TODO |

---

## Part 9: Key References

### Academic Papers

1. **Network Dynamics in Mixed Martial Arts: A Complex Systems Approach to UFC Competition Insights** (arXiv:2502.07020, Feb 2025)
   - Complex network analysis of UFC matchmaking evolution
   - Degree distribution, clustering, betweenness centrality
   - Key finding: UFC transitioned from clustered to decentralized networks

2. **Centrality Measure - Overview** (ScienceDirect)
   - Standard definitions of degree, eigenvector, betweenness, closeness
   - Application to social and competitive networks

3. **Hierarchical Dirichlet Processes** (Blei Lab, Harvard)
   - Mathematical foundation for HDP
   - Clustering with unknown number of categories

4. **Graph Attention Networks** (Velickovic et al., ICLR 2018)
   - Attention mechanism for graph neural networks
   - Weighted neighbor aggregation

### Online Resources

5. **PageRank for MMA Rankings** (LinkedIn MMA Analytics Community)
   - Treating losses as "passing" relevance
   - Cross-weight-class comparisons

6. **Analyzing UFC Fighter Network Using Graph Centrality in Rust** (LinkedIn Learning)
   - Closeness centrality applied to UFC network
   - Practical implementation example

### Libraries and Tools

7. **PyTorch Geometric** (pyg.org)
   - GNN framework with GAT, TGN, and link prediction support

8. **bnpy** (github.com/bnpy/bnpy)
   - Bayesian nonparametric inference in Python

9. **NetworkX** (networkx.org)
   - Graph analysis and community detection in Python

---

## Part 10: Next Steps

### Immediate (After Crawl Completes)

1. **Run all centrality queries on full dataset** - Currently limited by partial data
2. **Add NetworkX visualization** - Export graph for visual analysis with Gephi
3. **Implement community detection** - Louvain algorithm on fight graph
4. **Build DAG flow analysis** - Identify gatekeepers and prospect-feeders

### Short Term (1-2 Weeks)

5. **Scrape gym affiliations** - Tapology/Wikipedia for gym data
6. **Build bipartite gym graph** - Fighter <-> Gym relationships
7. **Implement transitivity over time** - Track clustering coefficient by year
8. **Temporal decay centrality** - Weight recent fights more heavily

### Medium Term (1-2 Months)

9. **Scrape historical betting odds** - OddsPortal or similar
10. **Build GAT prototype** - PyTorch Geometric on exported graph
11. **HDP style discovery** - Cluster fighters by in-fight micro-data
12. **Market inefficiency detection** - Compare model vs betting market

### Long Term (3-6 Months)

13. **Full GNN pipeline** - Train, validate, deploy prediction model
14. **Bayesian GNN** - Uncertainty quantification for betting edge
15. **PPV prediction model** - Link prediction with revenue estimation
16. **Real-time dashboard** - Streamlit dashboard with live predictions
