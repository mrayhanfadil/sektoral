# Method / stage overrides
File per ticker: `<TICKER>.json`
Fields: life_cycle_stage, has_steady_state_3y, commodity_price_driven,
dissimilar_segments, method, method_reason|reason, analyst, date
Example:
{"life_cycle_stage": "mature", "has_steady_state_3y": true,
 "commodity_price_driven": false, "dissimilar_segments": 1,
 "method": "fcff_dcf", "reason": "kualitas aset inti", "analyst": "A", "date": "2026-09-24"}
