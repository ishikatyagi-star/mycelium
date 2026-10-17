import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def nid(label: str, key) -> str:
    """Stable node id used in API paths (front-end graph keys)."""
    return f"{label}:{key}"
