# Rating history store
File per ticker: `<TICKER>.json`
Format: {"history": [{"date": "2026-08-20", "rating": "Buy", "tp": 2500}]}
Cover status:
- No history -> "Inisiasi"
- Same rating as last -> "Dipertahankan"
- Upgrade (Sell->Hold, Hold->Buy, Sell->Buy) -> "Naik dari X"
- Downgrade -> "Turun dari X"
