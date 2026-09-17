from slugify import slugify as _slugify


def make_slug(text: str) -> str:
    return _slugify(text, separator="-", lowercase=True)
