# 063 — Doctor and vault health in the Settings footer

> **Status: Accepted (2026-10-03), designed with damiro.** Builds on ADR 029 (`sympose doctor`) and ADR 034 (`sympose vault --health`). `vault --draft` is left in the terminal on purpose.

## Context

`sympose doctor` and `sympose vault --health` exist only in the terminal. A person who uses the web app has no way to ask whether the installation or the notes are in order, and neither command has an endpoint, so the web app could not ask even if it wanted to.

## Decision

**Two pills at the far left of the Settings footer**, "Doctor" and "Vault health", in the same style and height as the light/dark pill at the far right. Nothing runs until a pill is clicked: the doctor loads a model library and the health check reads the whole vault, so neither runs when Settings opens and neither shows a count or a dot beforehand.

**A clean result is a notification, a finding is a dialog.** A click runs the check. When nothing is wrong, the app says so in a notification (the same one it uses elsewhere) and no dialog opens: there is nothing to choose. When something is wrong, a dialog lists the findings.
- *Doctor* shows which models are in use and whether anything leaves the computer (the lines the terminal prints first), then each problem. When at least one can be fixed, the dialog offers **Fix** and **Decline**. Fix does exactly what `sympose doctor --fix` does (persona folders and the settings file, never the notes), and the result (what was fixed and what is left) comes back as a notification, or in the dialog if something is still left. With nothing fixable there is only Close.
- *Vault health* shows the same report as the terminal (problems first, then offers), for the default persona only, with only Close: it changes nothing and has nothing to fix. A vault with only offers (a folder that could be defined) and no problem counts as clean and gets the notification.

**One engine, two surfaces.** The terminal and the web read the same results. `doctor.examine(fix)` returns every finding with its state (needs you, fixable, fixed, could not fix) and `doctor.run` prints from it, so the terminal's output is unchanged. `vault_health.scan` is already structured. Three endpoints: `GET /api/doctor` (reads only), `POST /api/doctor/fix`, `GET /api/vault/health`. They answer with the structure, not printed text, so the browser holds no wording of its own about what a finding means.

## Consequences

- The terminal and the web app offer the same two checks (the standing parity rule), with `--draft` as the one deliberate exception: it calls a model and writes a note, which belongs behind the persona write path (#21), not a footer pill.
- The doctor request takes a few seconds the first time (the model library loads); the dialog says it is checking.
- Fix is the only write, it is a click on an explicit button, and what it may change is the same short list ADR 029 fixed.

## Alternatives rejected

- **Showing a result on the pill when Settings opens.** It would run both checks on every visit and pay the library load for a footer.
- **Parsing the terminal's printed text in the browser.** A change in wording would silently break the dialog; structured results cannot.
- **Health for any persona.** The terminal's default persona is what a person means by "my vault"; choosing one is a later addition if asked for.
