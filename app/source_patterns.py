"""English for Indonesian text the model builds before the prose stage.

Forecast, valuation and intake write short basis and reason strings
(``payout_basis``, ``dps_basis``, method-chain reader reasons, …) once, in
Indonesian, before ``app.build`` runs the prose stage in two languages; a
template quotes them through ``prose_lang.source``. Each entry is a pattern
over the whole Indonesian string and its English template; the groups carry
figures and names through unchanged, so the English states the same figures.
"""
import re

PATTERNS = [(re.compile(p), t) for p, t in (
)]
