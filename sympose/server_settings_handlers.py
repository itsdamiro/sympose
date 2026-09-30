"""The engine settings' route handlers (docs/decisions/044): the same list the terminal's `/settings`
shows, described to the browser and changed through the same rules (`engine.settings_apply`), so the
web app holds no rule of its own. A value the owning module refuses is answered with 422 and the
reason, and left as it was."""

from typing import Any

from fastapi import HTTPException

from sympose import settings_store
from sympose.engine import settings_apply
from sympose.engine.settings_registry import GROUPS, NUMBER, SETTINGS, Setting, find
from sympose.server_models import SettingChange


def _row(setting: Setting) -> dict[str, Any]:
    return {
        "key": setting.key,
        "kind": setting.kind,
        "summary": setting.summary,
        "value": setting.current(),
        "text": settings_apply.value_text(setting),
        "default": setting.default(),
        "is_default": settings_store.get(setting.key) is None,
        "choices": list(setting.choices),
        "hint": setting.hint,
        "whole": setting.whole,
    }


def get_settings() -> dict[str, Any]:
    return {"groups": [{"name": g, "settings": [_row(s) for s in SETTINGS if s.group == g]} for g in GROUPS]}


def put_setting(key: str, body: SettingChange) -> dict[str, Any]:
    setting = find(key)
    if setting is None:
        raise HTTPException(status_code=404, detail=f"There is no setting called {key}.")
    if setting.kind == NUMBER:
        message, ok = settings_apply.set_number(setting, "" if body.value is None else str(body.value))
    else:
        wanted = setting.default() if body.value is None else body.value
        message, ok = settings_apply.set_value(setting, wanted)
    if not ok:
        raise HTTPException(status_code=422, detail=message)
    return {"message": message, "setting": _row(setting)}
