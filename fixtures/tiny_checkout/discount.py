def apply_percentage_discount(price: float, percent: float) -> float:
    # BUG: percent is being treated as an absolute amount.
    return price - percent
