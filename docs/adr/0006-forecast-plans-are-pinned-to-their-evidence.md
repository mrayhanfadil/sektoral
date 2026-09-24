# Forecast Plans are pinned to their evidence

A validated Forecast Plan is stored under a fingerprint of its evidence (official release, dated headlines, spec version and model) and reused while that fingerprint is unchanged. Rerunning a ticker on the same evidence therefore gives the same Target Price instead of drifting with each LLM sample. New evidence triggers a fresh agent pass, and an explicit flag can force one.
