import uuid
import secrets


def make_id(prefix: str) -> str:
    """Generate a prefixed short ID like usr_a3f9, plt_1bc2."""
    return f"{prefix}_{secrets.token_hex(4)}"


def make_uuid() -> str:
    return str(uuid.uuid4())
