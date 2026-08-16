def clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def safe_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0
