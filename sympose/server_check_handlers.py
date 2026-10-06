"""Route handler logic for the Settings footer's two checks (docs/decisions/063): `sympose doctor` and
`sympose vault --health`, answered as structure so the browser holds no wording of its own. The doctor's
`GET` only reads; its `POST` applies the fixes `sympose doctor --fix` would. Health reads as the default persona."""

from typing import Any

from fastapi import HTTPException

from sympose import doctor, folder_looks_write, vault_health, vault_health_report
from sympose import profile as profiles


def _doctor(fix: bool) -> dict[str, Any]:
    from sympose import doctor_models  # imported here: it brings in litellm, a few seconds

    return {
        "models": doctor_models.report(),
        "findings": [{"problem": o.problem, "state": o.state, "fix": o.fix, "error": o.error} for o in doctor.examine(fix)],
    }


def get_doctor() -> dict[str, Any]:
    return _doctor(False)


def fix_doctor() -> dict[str, Any]:
    return _doctor(True)


def get_vault_health() -> dict[str, Any]:
    found = profiles.resolve_profile(None)
    if found is None:
        raise HTTPException(status_code=409, detail="No default persona was found. Run `sympose doctor` in a terminal to see why.")
    scanned = vault_health.scan(found)
    if scanned is None:
        raise HTTPException(status_code=409, detail="No vault is set up yet. Set VAULT_PATHS in your .env file to the folder of your Obsidian vault (see .env.example).")
    scope, results = scanned
    return {
        "persona": found.get("handle", ""),
        "notes": len(scope.notes),
        "problems": vault_health_report.problem_count(results),
        "limits": vault_health_report.LIMITS,
        "checks": [
            {
                "heading": check.heading,
                "problem": check.problem,
                "findings": [{"note": f.note, "message": f.message, "folder": f.folder, "adds": list(f.fix)} for f in findings],
            }
            for check, findings in sorted(results, key=lambda r: not r[0].problem)
            if findings
        ],
    }


def add_folder_look(folder: str) -> dict[str, Any]:
    """The fix the health offers for one folder's definition (ADR 064), applied on the user's click: the property
    lines written, or why not. As with the report, the default persona."""
    found = profiles.resolve_profile(None)
    if found is None:
        raise HTTPException(status_code=409, detail="No default persona was found. Run `sympose doctor` in a terminal to see why.")
    try:
        return {"folder": folder, "added": folder_looks_write.add_look(found, folder)}
    except folder_looks_write.Refused as reason:
        raise HTTPException(status_code=409, detail=str(reason)) from reason
