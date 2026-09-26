# Reports that clear the automatic gates publish at once

Supersedes the review-gated part of [0009](0009-publication-uses-an-approved-frozen-bundle.md).

Sektoral exists so that retail readers can reach a sourced fair-value analysis without building a model. Every check that makes a report trustworthy runs automatically on each build: dated official evidence, the share and normalization ledgers, terminal economics, the independent reference model, template tie-outs and the house policy. A mandatory manual attestation mostly repeated those checks and held every report back until someone filled a 15-item form. Under 0009, readers saw only "menunggu review".

Release policy 1.3.0 therefore publishes a Production-Ready or Assumption-Led report as soon as it clears the gates. The report is labelled "Terbit otomatis · belum direview analis", and its forecast is frozen in the forecast ledger at build. An authenticated reviewer approval is optional. It adds the "Terbit · direview analis" badge and archives the hash-verified bundle, as 0009 describes. The reviewer starts from a draft attestation written from the report's own evidence and declares their own issuer relationship and conflicts.

A draft (`draft_non_distributable`) is never published. `SECTORAL_AUTO_PUBLISH=0` restores review-gated publication. As in 0009, this is not a claim of regulated research status: presenting fair values and ratings to the public still needs the Indonesian legal and compliance review tracked as decision D10.
