"""The skill routes' handlers (docs/decisions/077, the amendment of 2026-10-14): a persona's skills listed, one read before
it is switched on, a folder added (copied in, off) and a skill switched on or off. The rules are `persona_skills`'; a
request it refuses is a 422 with the reason, and an unknown persona or skill a 404."""

from typing import Any

from fastapi import HTTPException

from sympose import persona_skills
from sympose.server_models import SkillAdd, SkillSwitch


def _refused(error: persona_skills.SkillRefused, missing: bool = False) -> HTTPException:
    return HTTPException(status_code=404 if missing else 422, detail=str(error))


def list_skills(handle: str) -> dict[str, Any]:
    try:
        return {"skills": persona_skills.listing(handle)}
    except persona_skills.SkillRefused as e:
        raise _refused(e, missing=True) from None


def get_skill(handle: str, name: str) -> dict[str, Any]:
    try:
        return persona_skills.read(handle, name)
    except persona_skills.SkillRefused as e:
        raise _refused(e, missing=True) from None


def post_skill(handle: str, body: SkillAdd) -> dict[str, Any]:
    try:
        return persona_skills.add(handle, body.folder)
    except persona_skills.SkillRefused as e:
        raise _refused(e) from None


def put_skill(handle: str, name: str, body: SkillSwitch) -> dict[str, Any]:
    try:
        return {"skill": persona_skills.set_enabled(handle, name, body.enabled)}
    except persona_skills.SkillRefused as e:
        raise _refused(e) from None
