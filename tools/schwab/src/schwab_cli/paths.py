from urllib.parse import urlparse


def normalize_api_path(path: str) -> str:
    trimmed = path.strip()
    if trimmed.startswith("http://") or trimmed.startswith("https://"):
        parsed = urlparse(trimmed)
        trimmed = parsed.path
        if parsed.query:
            trimmed = f"{trimmed}?{parsed.query}"
    if not trimmed.startswith("/"):
        trimmed = f"/{trimmed}"
    return trimmed


def assert_get_path_allowed(path: str) -> str:
    normalized = normalize_api_path(path)
    lower = normalized.lower()
    if "orders" in lower:
        msg = "Refusing request: paths containing 'orders' are not allowed."
        raise ValueError(msg)
    return normalized
