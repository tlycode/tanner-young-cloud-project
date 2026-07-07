# app/tag_utils.py

from app.models import db, Tag

MAX_TAG_LENGTH = 50


def parse_tag_names(raw):
    if raw is None:
        return []
    parts = raw.split(',') if isinstance(raw, str) else raw
    seen, result = set(), []
    for part in parts:
        name = part.strip().lower()[:MAX_TAG_LENGTH]
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def get_or_create_tags(names):
    if not names:
        return []
    existing = {t.name: t for t in Tag.query.filter(Tag.name.in_(names)).all()}
    tags = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.session.add(tag)
            existing[name] = tag
        tags.append(tag)
    return tags
