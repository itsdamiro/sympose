# 053. The app shell is split by concern

Status: Accepted (damiro, 2026-10-01). Splits #95; the cancel-a-reply part of #95 is not a split and is filed on its own.

## Context

`ui/src/routes/app-shell.tsx` is 1860 lines and one function, `AppShell`, of about 1500. It owns the section history and the phone menu, the vault list and switching, the tree and the hidden list, the open note, search, creating notes and folders, the tree's actions, the pinned and recent lists, the nebula stage, the persona roster and everything the chat needs, and about 380 lines of markup for the content panel's toolbar and body. ADR 044 named it as the one place where modularity had slipped, and said chat state must not go into it; the chat did get its own hook (`useChat`), but the shell kept growing around it.

The cost is practical: a change to search risks the history stack, nothing in it can be tested without a browser, and each hook added to the file makes the next harder to place.

## Decision

Every concern becomes its own module, and `AppShell` is left to compose them and lay out the panels. This is a behaviour-preserving move: no setting, cookie, request or pixel changes.

- **A hook per concern, a component per block of markup.** Hooks go in `ui/src/lib/` as `use-*.ts` (like `use-chat`, `use-pinned-notes`), components in `ui/src/components/sympose/`. A hook takes what it needs as parameters and returns plain values and callbacks; it does not reach into another hook's state.
- **Not a file per function.** The unit is a concern: the history stack, its `goBack` and `goForward` and the slide direction live together, because splitting them would only spread one idea across files.
- **Order of declaration is kept** where it can matter (effects run in the order hooks are declared), and the one state that many concerns write, the refresh counter that makes the tree, graph and search re-fetch, becomes one small hook (`useVaultRefresh`) with a stable `refresh`, instead of `setVaultRefreshKey((k) => k + 1)` repeated in a dozen places.
- **About 250 lines per file as a guide** (the Python cap is 200; a few lines over is fine where cutting would not be practical).
- **The slices**, each its own change with every gate green: the search result row; link and open-note handling (`use-link-sources`, `use-note-opening`); the nebula stage; the section history and the shell navigation (phone menu, `selectSection`); the menu's collapse state; the tree and the hidden list; the vault list and switching, and the open note; search; creating notes and folders; the tree's actions and the folder view's derived lists; the persona roster and the chat bundle; the content toolbar and the content body as components; last, the shell itself.
- **How each slice is checked.** A click-through in headless Chrome on a scratch vault, run before the first slice and after every one, compared snapshot by snapshot (headings, visible buttons with their pressed and disabled state, the panels' positions, the `sympose:shell`, `vault` and `pref` cookies, notices), on a desktop and a phone viewport; the click-through is deterministic, so any difference is a change. A hook that holds real logic (the history stack, the search derivation, the open-note rules, the pinned and recent lists) also gets its own test, mutation-checked. jsdom alone is not trusted for layout and animation.

## Consequences

- `app-shell.tsx` ends near 300 lines; the pieces can be read, tested and changed on their own.
- The shell has no tests of its own today; the extracted hooks gain them. The click-through lives outside the repo (as the other browser recipes do), so a later change to the shell is checked by the hooks' tests and a manual click-through, not by CI.
- Reading the code, one more file to open per concern; in exchange none of them is longer than a screen or two.

## Alternatives rejected

- **A single "shell state" context or store.** It would move the 1500 lines somewhere else and make every component depend on all of it.
- **One file per function.** More files than ideas; the history stack alone would take four.
- **Leave the shell and close #95.** Rejected by damiro: the file keeps growing and cannot be tested.
- **Rewrite the chunks while moving them.** A move that also changes behaviour cannot be checked by a snapshot diff; behaviour changes (cancelling a reply in flight, the cookie-preference hook, `markdown-panel`'s own animation state) are separate issues.
