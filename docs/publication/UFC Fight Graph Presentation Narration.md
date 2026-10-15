# UFC Fight Graph Presentation Narration

[Explore the live dashboard](https://ufc-fight-graph.streamlit.app/)

Twelve-slide YouTube walkthrough with narration and screen cues. Allow about 9 to 11 minutes, including dashboard demonstrations.

## Slide 1 UFC Fight Graph

**On screen:** Open on the title, then introduce the Streamlit deployment.

I rebuilt UFC Fight Graph after the database was lost. In this walkthrough, I will show the connected archive that came out of that rebuild and explain the engineering decisions behind it. The project uses Python to collect UFCStats records, Neo4j to store their relationships, and Streamlit with Plotly to make them explorable. I will also show the parts of the source that remain incomplete, particularly judge information. The figures in this presentation describe the completed snapshot reviewed on 13 October 2026.

**Source:** README.md; docs/ARCHITECTURE.md; completed crawl record

## Slide 2 The completed archive

**On screen:** Show Explore then Overview. Pause on the four headline counts.

The archive contains 8,935 fights, 4,628 fighter profiles and 792 events. The 719 officials shown here combine 249 referees and 470 judges. The overview gives me a quick sense of the recorded history through a yearly fight-count chart and a breakdown of how fights ended. This is a dated source snapshot. In particular, the final year in the timeline covers only the events available at the time of the crawl, so I would not compare that point with a complete prior year as evidence of a decline. The charts are a way into the records underneath.

![8,935 fights across 792 events](../images/overview.jpg)

*8,935 fights across 792 events*

**Source:** Live dashboard capture on 13 October 2026; UFCStats archive

## Slide 3 Why the rebuild began with cleanup

**On screen:** Explain the audit. Optionally show docs/AUDIT.md in the repository.

Before rebuilding the data, I inspected the code and the commit history. A previous refactor had introduced new modules while retaining their predecessors. That left duplicate crawl paths and separate dashboard implementations. Some abstractions also remained in the repository without any application code importing them. I consolidated the running paths and removed obsolete material. The audit documentation explains the changes, while Git retains the earlier revisions. The purpose was to make the actual application easier to understand, so future repairs would have one clear place to go.

**Source:** docs/AUDIT.md; commits 518bd76 and e1966a6

## Slide 4 The graph model

**On screen:** Explain one bout as the link between participants, event and officials.

The fight is the central record. A fighter connects to it through a participation relationship that stores the result. The fight connects to an event, and that event connects to a location. Separate relationships link the fight to its weight class, referee and judges. The judge relationship stores the published total. Fighter URLs act as identities, which matters when two people share a name. Across the complete snapshot, the graph contains 15,360 nodes and 57,759 relationships. This structure lets the interface move naturally between a person's history and the events and officials attached to it.

**Source:** docs/ARCHITECTURE.md; final backup manifest

## Slide 5 Following a fighter through opponents

**On screen:** Choose Explore then Fighter explorer, select Jon Jones and open Opponent network.

Here is one visible use of those connections. In Fighter explorer, I select Jon Jones and open the opponent network. The centre represents the selected fighter. Each surrounding node represents an opponent, and the node size reflects repeated meetings in the stored archive. This view displays up to 12 frequent opponents. I can switch to fight history to inspect the underlying bouts. The career record on a profile may include fights outside this imported UFC history, so the career total and the archive bout count answer different questions. I keep that explanation in the interface.

![Fighter explorer shows up to 12 frequent opponents](../images/opponent-network.jpg)

*Fighter explorer shows up to 12 frequent opponents*

**Source:** Live fighter explorer capture; web/explorer.py; web/charts.py

## Slide 6 Resuming the crawl safely

**On screen:** Explain the sequence without showing credentials or local configuration.

The crawler starts with events, enriches eligible fights from the detail pages, and then loads fighter profiles. It records progress only after the database accepts the corresponding write. If a request fails, the URL remains eligible for a later attempt. That means I can resume unfinished work without discarding records that already loaded. I increased HTTP concurrency during the remaining crawl while keeping database writes and checkpoint changes serial. Each worker has its own session and pacing. The important claim is that the crawl continued from its saved progress. I have not presented a controlled performance benchmark for the speed change.

**Source:** run_crawl.py; infrastructure/checkpoint.py; docs/ARCHITECTURE.md

## Slide 7 Referees across the archive

**On screen:** Open Officials then Referee desk and show the selected referee and coverage counts.

Referee information now forms part of the rebuilt graph. This snapshot has 249 named referees and a referee recorded for all 8,935 fights. The Referee desk shows the assignment history for the selected official and a breakdown of the recorded outcomes. It also offers a minimum-fight threshold for the leaderboard. Those outcome percentages describe the assigned fights. Different matchups and sample sizes affect them, so I use this page to explore records and distributions rather than infer the quality of a referee's decisions from a finish rate.

![249 referees with assignments on all 8,935 fights](../images/referees.jpg)

*249 referees with assignments on all 8,935 fights*

**Source:** Live referee dashboard capture; docs/DATA_OPERATIONS.md

## Slide 8 Published judge totals

**On screen:** Open Judge scorecards. Show the selected judge's frequent totals and fight list.

The judge page gives another route through the data. It lets me inspect the published totals associated with a named judge and open the corresponding fight record. The headline number is 4,064 fights with at least one named scorecard. That includes 4,041 decision fights plus 23 overturned results that retain scorecards. These are final totals, rather than a round-by-round breakdown. A completed fetch does not make the source complete, so I checked the decision population separately. The next slide shows exactly how much named-judge coverage the current source provides.

**Source:** Live judge dashboard capture; docs/DATA_OPERATIONS.md#judge-coverage

## Slide 9 Decision fight coverage

**On screen:** Pause on the three coverage groups and explain the anonymous totals.

Of the 4,139 decision fights, 4,034 have all three named judges and their totals. Seven have only one or two named judges. Another 98 have no named judges. Within those 98, the raw fight details retain anonymous score totals for 42 fights, while 56 have no totals recorded. Spot-checking UFCStats confirmed missing names or empty details on the source pages. The next enrichment task therefore needs additional sources and provenance for any new information. I have kept this gap visible in the documentation instead of treating a completed crawl as evidence that every judging field is available.

**Source:** docs/DATA_OPERATIONS.md#judge-coverage; judge coverage audit

## Slide 10 Event geography

**On screen:** Open Analysis then Geographic insights. Toggle Events and Fights, then select a country.

The geography view maps where the recorded events took place. This snapshot includes 175 host locations across 31 mapped countries and territories. The Plotly map can display event counts or fight counts. Selecting a country narrows the location table and the fight-method charts below it. I also adjusted the charts so long category labels wrap and the axes have room to display them. The map represents hosting activity in the imported archive. It is not a measure of a country's fighter population or the popularity of the sport.

![175 host locations across 31 countries and territories](../images/geography.jpg)

*175 host locations across 31 countries and territories*

**Source:** Live geography dashboard capture; web/geography.py; web/app.py

## Slide 11 A restorable graph backup

**On screen:** Explain the archive contents. Keep backup credentials and private Drive identifiers off screen.

The database loss made recovery a central part of the rebuild. The backup ZIP contains graph JSON and a manifest with counts and a checksum. It preserves node labels and properties as well as typed relationships and their endpoints. The graph JSON is about 17.21 megabytes and compresses into a ZIP of about 1.25 megabytes. These are export sizes, rather than the size of the Neo4j store. The restore command targets an empty database. After crawl writes stopped, the final snapshot exported and a local rclone uploader sent it to Google Drive and verified the copy. The uploader runs independently of the AI chat while the machine stays running and connected.

**Source:** run_backup.py; run_upload.py; final ZIP manifest and verified upload receipt

## Slide 12 Using and extending the project

**On screen:** Show the repository README and finish with the invitation for feedback.

The Streamlit deployment is online, and the live dashboard link is in the video description. The repository includes setup steps, the graph schema and operations instructions. The next data improvement is completing judge coverage with traceable additional sources. I also want the interface to keep its metric definitions clear, especially where career averages cover a wider history or network rankings use heuristics. If you explore the app, I would welcome feedback on the data model and the questions you would want the dashboard to answer. The repository link is in the video description.

**Source:** README.md; docs/NETWORK_RESEARCH.md; docs/DATA_OPERATIONS.md

## Project links

- [Live dashboard](https://ufc-fight-graph.streamlit.app/)
- [Project repository](https://github.com/TheAlchemistNerd/ufc-fight-graph)
- [Graph architecture](https://github.com/TheAlchemistNerd/ufc-fight-graph/blob/main/docs/ARCHITECTURE.md)
- [Judge coverage and recovery](https://github.com/TheAlchemistNerd/ufc-fight-graph/blob/main/docs/DATA_OPERATIONS.md#judge-coverage)
- [Code and history audit](https://github.com/TheAlchemistNerd/ufc-fight-graph/blob/main/docs/AUDIT.md)
- [Analytics definitions](https://github.com/TheAlchemistNerd/ufc-fight-graph/blob/main/docs/NETWORK_RESEARCH.md)
- [UFCStats source archive](http://ufcstats.com/statistics/events/completed?page=all)
