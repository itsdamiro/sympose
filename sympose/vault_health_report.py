"""The text of `sympose vault --health` (docs/decisions/034): findings grouped by check and, inside a check, by
top-level folder, so a folder where every note is affected is one line and not a page.

Note names are in it, so it is printed to the terminal and nowhere else."""

from collections import Counter

from sympose.vault_health import Check, Finding, Scope, folder_of

SHOWN_PER_FOLDER = 3
ROOT = "(vault root)"
LIMITS = "Limits: only [[wiki links]] are checked."


def _folder_lines(findings: list[Finding], totals: Counter, of_notes: bool) -> list[str]:
    by_folder: dict[str, list[Finding]] = {}
    for finding in findings:
        by_folder.setdefault(finding.folder, []).append(finding)
    lines = []
    for folder, group in sorted(by_folder.items(), key=lambda item: (-len({f.note for f in item[1]}), item[0].lower())):
        affected = len({f.note for f in group})
        count = f"{affected} of {totals[folder]} notes" if of_notes else f"{affected} file{'s' if affected != 1 else ''}"
        lines.append(f"  {folder or ROOT}: {count}")
        lines += [f"    {f.note}: {f.message}" for f in group[:SHOWN_PER_FOLDER]]
        if len(group) > SHOWN_PER_FOLDER:
            lines.append(f"    and {len(group) - SHOWN_PER_FOLDER} more")
    return lines


def render(scope: Scope, results: list[tuple[Check, list[Finding]]]) -> list[str]:
    """The report's lines; problems first, then the offers and observations."""
    totals = Counter(folder_of(n["rel_path"]) for n in scope.notes)
    lines = [f"Vault health: {len(scope.notes)} notes read as {scope.profile.get('handle', 'the persona')}.", ""]
    for check, findings in sorted(results, key=lambda r: not r[0].problem):
        if findings:
            body = [f"  {f.message}" for f in findings] if not check.per_folder else _folder_lines(findings, totals, check.of_notes)
            lines += [f"{check.heading} ({len(findings)})", *body, ""]
    problems = problem_count(results)
    lines.append(f"{problems} problem(s) found." if problems else "Nothing wrong found.")
    return lines + [LIMITS]


def problem_count(results: list[tuple[Check, list[Finding]]]) -> int:
    return sum(len(findings) for check, findings in results if check.problem)
