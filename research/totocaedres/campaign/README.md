# Continuous discovery campaign

The worker cycles indefinitely through the necessary principal-problem
signatures for genera 0 through 3. It first inserts the exhaustive low-genus
`K4` and `K7` maps, then samples bounded rotation systems for the configured
`(g,F,M,D,H)` signatures. Every new valid topology is stored before geometry
is attempted. Trivalent disk maps use map-derived symmetry plane search and an
exact rational certificate; other maps use the numerical planarity solver.

The process is resumable and offline. Runtime files live under
`campaign/runtime/`:

- `state.json`: atomic status snapshot;
- `events.jsonl`: append-only event log;
- `candidates/*.json`: topology and geometry records;
- `STOP`: graceful-stop request;
- `runner.lock`: prevents two workers using one runtime directory.

Geometry work is quota-balanced by genus. A backlog of pending maps is drained
across later cycles, so abundant spherical maps cannot starve genera 2 and 3.

Commands from the repository root:

```powershell
.\start_campaign.bat
.\status_campaign.bat
.\stop_campaign.bat
```

The campaign has no natural terminal condition. Budgets increase slowly with
the cycle number, and signatures are visited round-robin by genus. This is an
unbounded heuristic campaign, not a claim of exhaustive enumeration for
genera 2 and 3. The exact `K4` and `K7` stages are exhaustive up to
isomorphism within their documented scope.
