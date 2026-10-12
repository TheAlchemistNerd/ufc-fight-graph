# Analytics definitions

The dashboard reports descriptive statistics from the imported graph. Referee
coverage is shown alongside outcome rates. Judge scores are fight totals; a large
total margin does not establish that a judge awarded an individual 10–8 round.

| Metric | Definition |
|---|---|
| Degree | Distinct opponents, with win percentage from the same imported fights |
| Opponent influence proxy | Direct opponents × distinct two-hop reach / 100 |
| Win-network proxy | Distinct defeated opponents × their opponent reach / 100 |
| Bridge proxy | Pairs of a fighter's opponents who have never fought each other |
| Reach multiplier | Distinct two-hop reach divided by direct reach |
| Division density | Unique unordered matchups / possible unordered fighter pairs; rematches do not inflate density |
| Separation | Shortest Fighter–Fight path length / 2, within three opponent hops |
| Rebound rate | Outcome of the next chronologically recorded fight after each loss |
| Title finish rate | KO/TKO or submission finishes among fights explicitly marked as title bouts |

Influence, win-network and bridge scores are heuristics, not eigenvector centrality,
PageRank or shortest-path betweenness algorithms. Current career records include
bouts outside the imported sample. Birth-decade charts describe fighters' current
career averages, not historical per-fight performance in each decade.

Future research can add exact graph algorithms, opponent-adjusted comparisons or
per-round features once their data and evaluation requirements are implemented.
Earlier speculative research and marketing material remains available in Git history.
