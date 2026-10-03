"""Route handler logic for the Settings footer's two checks (docs/decisions/063): `sympose doctor` and
`sympose vault --health`, answered as structure so the browser holds no wording of its own. The doctor's
`GET` only reads; its `POST` applies the fixes `sympose doctor --fix` would. Health reads as the default persona."""

from typing import Any

from fastapi import HTTPException

from sympose import doctor, vault_health, vault_health_report
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
        raise HTTPException(status_code=409, detail="The default persona cannot be found (run `sympose doctor`).")
    scanned = vault_health.scan(found)
    if scanned is None:
        raise HTTPException(status_code=409, detail="No vault is set up (see VAULT_PATHS in .env.example).")
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
                "findings": [{"note": f.note, "message": f.message} for f in findings],
            }
            for check, findings in sorted(results, key=lambda r: not r[0].problem)
            if findings
        ],
    }
