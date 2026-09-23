"""Production recommendation bands from the report specification.

Classification is only called after a release gate approves the underlying
target price. A numerical scenario alone is never a recommendation.
"""


def classify(upside):
    if upside > 0.15:
        return "Buy"
    if upside < -0.10:
        return "Sell"
    return "Hold"
