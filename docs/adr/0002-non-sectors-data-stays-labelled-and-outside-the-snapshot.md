# Data from other sources stays labelled and outside the Sectors Snapshot

When the snapshot lacks something, such as a peer's debt and cash for EV/EBITDA or 18-24 months of price history, we fill it from dated snapshots of Yahoo Finance or IDX trading summaries. That data is stored separately, never written into the Sectors Snapshot, and named by its real source in every exhibit. Merging it would be simpler, but a reader could no longer tell Sectors data from a gap-fill, and the claim "market data comes from Sectors" would quietly become false.
