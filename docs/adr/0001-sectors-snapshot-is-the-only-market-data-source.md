# The local Sectors Snapshot is the only market-data source

Agents and the report builder read market data only from the local Sectors Snapshot; no run calls the Sectors API, and a test asserts the analyst modules never import the network client. This keeps every run free of API credits and reproducible from the same rows. The cost is stale data: the snapshot never expires, a refresh is an explicit, credit-logged command, and a newer dated close enters only as a labelled Market Quote Override.

## Considered Options

- **Live Sectors API calls during a run**: rejected; each run would spend credits and two runs on the same Report Date could read different data.
