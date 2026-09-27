# 035 — A vault map and mechanical connections between notes, always in the prompt, computed from what already exists

> **Status: Accepted** (2026-09-27, after the design talk with the vault owner on issue #78). Not built yet; this record comes first, as the standards ask. Settles the first slice of #78 — the vault map (layer 1) and mechanical connections (layer 3's non-embedding half). Layer 3's meaning-based connections and layer 4's on-demand numbers stay open on #78 for later work.

## Context

Today the persona knows only what one turn's search happens to surface. She has no built-in sense of the vault's shape (how many notes a folder holds, what it is generally about) unless a note about it happens to match, and no sense that a grounded note connects to others (shares a tag, sits in the same folder, is linked to or from) unless the search also surfaced the connected note on its own. A person glancing at the vault's folder tree or its graph view sees both instantly; she currently cannot.

Facts about the code as it stands:

- `vault_snapshot.get_vault_snapshot` and `vault_manifest_build.build` already compute, mtime-cached, exactly the facts this needs: per-note frontmatter and tags, a resolved link graph (`nodes`, `links`), and folder counts. The web app's tree (`get_vault_tree`) and the Knowledge Nebula (`get_vault_graph`) already read them fresh on every request with no extra cost worth naming. `vault_graph.py`'s own docstring is explicit that this is "navigation only — never a grounding source", so none of it reaches a turn's prompt today.
- The link graph already resolves a wikilink written inside frontmatter, not only in the body: `vault_manifest_build.build` scans `full_content` (the raw file text, frontmatter included) for `[[...]]` targets, so a property written as `company: "[[Acme]]"` is already a graph edge. A property written as plain text that *names* a note (`company: Acme`, no brackets) is a different, already-solved problem: ADR 030's property-value passages resolve it by name and record it as a `via: value` match; it is not a graph edge and does not need to become one.
- `folder_definitions.py` (`due_folders`, `template_for_folder`) and `engine/folder_purpose.py` (`propose`) already compute a folder's habits and, on request, its purpose paragraph (ADR 033, stages 1 and 2) — built for `sympose vault --draft`, called from nowhere else.
- ADR 031 already reserved two categories for exactly this feature, `vault_map` and `connections`, named but not yet meaningful (nothing populates them).
- ADR 015's prompt-fitting loop (`budget.fit`) sacrifices, in order, recaps, then whole history turns, then the lowest-scoring grounding passages; the soul, the engine rules and the new message are fixed ahead of that loop, in `build_system_prompt` and `build_user_turn` (`prompt.py`). Anything new has to pick a side of that line.

## Decision

**Scope of this record.** Layer 1 (the vault map) and layer 3's *mechanical* connections (links, backlinks, frontmatter links — both the bracketed and the named-value kind above — shared tags and aliases, same top-level folder). Layer 3's meaning-based connections (from the embeddings of ADR 027) and layer 4 (an arbitrary on-demand count, "how many notes mention X") are deliberately left out: the first mixes an exact, explainable fact with a fuzzy one in the same place before either has been measured alone, and the second is already settled on #78 and #21 as a round-trip-dial, tool-calling matter, not a default.

**No new machinery.** Both the map and the connections are computed fresh from the snapshot and manifest that already exist, the same way the tree and the graph read them: no background thread, no new cache file, no new database. A change to the vault is picked up the next time either is asked for — the same freshness guarantee the tree, the graph and the health report already give, and cheap for the same reason they are (folder names, counts, tags and a link list are facts already sitting in the files, not something a model computes).

**What the map holds.** Per top-level folder: its definition's purpose sentence when one exists (ADR 033) and its note count; the vault's totals; its most common tags. Every line is a count or a fact read off the vault, never invented — the same rule ADR 033's template already follows.

**Where the map sits.** In `build_system_prompt`, alongside the soul and the recaps — fixed, ahead of `budget.fit`'s sacrifice loop, so it is never dropped to make room. This is a deliberate choice against the grain of ADR 015's usual "sacrifice grounding first" order: the map's whole point is that the persona always knows the vault's shape, so silently dropping it under pressure would contradict the feature. It is kept small enough that this is a small, checked risk rather than a real one — a ceiling in the range of 150 to 300 tokens is the target for the vaults measured so far (the personal vault's 7 due folders, ADR 033), confirmed or corrected once it is measured, not assumed.

**What the connections hold, and where they sit.** For a grounded note, its strongest connections from the vault's existing links, backlinks, shared tags/aliases and same folder, ranked in that order (an explicit link is the strongest signal; a shared folder the weakest), capped at 3 per grounded note. They are appended to that note's own passage text, not sent as a separate block — so if the note itself is dropped to fit the window, its connections go with it for free, and `budget.py`'s sacrifice loop needs no new branch to know about them.

**Privacy.** The two categories ADR 031 already named, `vault_map` and `connections`, off by default like the other three; the same withheld-message and header pattern (`prompt_blocks.py`, the CLI header, `/share`) extends to them without a new mechanism.

**Hidden folders and notes (#80, not built).** Included in both the map and the connections, consistent with the persona already reading hidden content everywhere else (the vault owner's existing decision that hiding is visual-only, in the tree and the graph). #80's knob changes what is *drawn* in the web app, not what the persona knows; if that should differ, it is #80's call to make, not this record's.

**Measured before it ships.** Two things, neither of which needs a new mechanism to check: that the map and the connections measurably help on a small set of vault-shape and connection questions (the same style of check ADR 033's purpose paragraph got), and that time-to-first-token does not meaningfully regress against today's grounding-only baseline (ADR 015 and 018's numbers) — since neither layer adds a model call, a regression would mean the computation itself is too slow on a large vault, not a cost that was expected.

## Consequences

- The persona always carries a small, cheap, checked summary of the vault's shape, and a grounded note carries its nearest neighbors without needing the search to have found them separately.
- Nothing here adds a model call, a background job, or a new store: the map and the connections cost is a few extra mtime-cached reads, already paid for by the tree, the graph and the health report.
- The map takes a small, fixed slice of every prompt's budget whether or not the turn needs it, which is the cost of never dropping it; the connections cost is paid only by the notes that are actually grounded, so it scales with what a turn already sends.
- The `vault_map` and `connections` settings ADR 031 reserved become real, and a user who has approved neither still gets the ordinary conversation and reference passages with a cloud model, same as today.
- Meaning-based connections and on-demand counts stay explicitly open on #78, so this record does not have to be revisited to add them later — only extended.

## Alternatives rejected

- **Building meaning-based connections in the same pass.** Rejected: an exact, explainable fact (a real link, a shared tag) and a fuzzy one (close in an embedding space) answer different questions about a note, and measuring them together would make it hard to tell which one is doing the work if an answer looks wrong. Left for a second, separate pass.
- **A background-computed connections store, refreshed on vault change.** Rejected as needless cost: the facts involved (links, tags, folders) are already read fresh, cheaply, by the tree and the graph on every request; a store would add invalidation logic to solve a latency problem that measurement has not shown exists.
- **A separate "connections" item in `budget.fit`'s sacrifice loop.** Rejected: it would need a new branch in `budget.py` with its own drop order; riding inside the note's own passage means a note and its connections are sacrificed as one unit, for free, in code that already exists.
- **Letting layer 4 (an arbitrary count like "how many notes mention X") ride along in the map.** Rejected: the map is a fixed, small, always-present fact; a genuinely open-ended count needs a real query over the vault, which is a round-trip cost to weigh (#21), not something to precompute speculatively for every possible question.
- **A settings knob to turn the map or the connections off.** Rejected: neither adds a model call or a meaningful cost to weigh, so there is no tradeoff for a knob to express; the privacy-relevant control is the `cloud_share` categories, which already exist for this.

## Measured (2026-09-27, `ollama_chat/gemma2:9b`, a synthetic 74-note scratch vault, 4 top-level folders)

**Size and speed of the computation itself, not the model call.** The map for this vault is 78 tokens
(`budget.count_tokens`, margin included) — well inside the 150-to-300 target — and took 6.6 ms to build
cold, 0.3 ms warm (the mtime-identity cache hit). A note's connections took 2.5 ms cold, 0.3 ms warm. Both
are negligible next to a model call (seconds), so the risk ADR 015 measured — a long *prompt* being slow
to process — is not in play here: the map and connections add a little over 100 characters to the prompt
per turn, not a meaningfully larger one.

**The model used the map and a note's connections correctly, with no invented number.** Asked "roughly
how many notes do you have about people, and what is that folder generally about?" (nothing in the
message would have found `People/People.md` by search), the reply was "You have 20 notes in the 'People'
folder. It's about people you know: friends, family and colleagues." — the exact count and the exact
purpose sentence the map carried, TTFT 4.8 s (in the range ADR 015 measured for prompts of this size on
this model, and not attributable to the map: the map's own build cost above is a rounding error against
it). Asked "who is Anna connected to in my notes?", the reply was "According to your notes, Anna is
connected to Ben, Cara, and Dee." — exactly the three names `connections.for_hits` computed (one real
link, two same-folder fallbacks, since the scratch vault's tag frontmatter did not parse as written; not
a code defect, the throwaway generator script's own bug), TTFT 3.8 s. Neither reply named a folder, a
count or a connection the map or the note's own passage did not state.

**Not measured:** other local models, a cloud model, a vault with more top-level folders than
`MAX_FOLDERS_SHOWN`, and side-by-side TTFT against the exact pre-035 prompt (the isolated timings above
stand in for it, since the difference between the two prompts is only the ~100 extra characters measured).

## Built (2026-09-27)

`sympose/vault_map.py` (`build`, mtime-identity cached like `folder_definitions`' own reads) and
`sympose/engine/connections.py` (`for_hits`, its link/label/folder index cached the same way, and the link
graph itself — `vault_graph.get_vault_graph`, which is rebuilt fresh on every one of its own callers —
cached here too, so a chat turn does not pay a full manifest rebuild that nothing was asking it to pay
before). `folder_definitions.read_purpose` reads a definition's purpose paragraph back out (the
counterpart of the existing `read_template`). Two new `cloud_share` categories, `VAULT_MAP` and
`CONNECTIONS`, in `engine/sharing.py`; `gate` now strips a hit's `connections` field (not the hit) when
that category is not approved, and `categories_of` takes a `vault_map` flag. `prompt_text.py` carries the
map's label and both categories' withheld sentences; `prompt_blocks.py`'s `vault_map_block` and the
connections line inside `_text_of`; `prompt.build_system_prompt`/`build_messages` take `vault_map` and
`vault_map_withheld`, constant across every attempt of `budget.fit`'s sacrifice loop. `turn.py` computes
the map and attaches connections once per turn, ahead of `sharing.gate`, so both are gated the same way
notes and properties already are.

**Tests.** 45 new (`test_vault_map.py`, `test_engine_connections.py`, plus additions to
`test_folder_definitions.py`, `test_engine_prompt.py`, `test_engine_sharing.py`, `test_engine_turn.py`),
1718 pass in all, ruff clean, and four existing tests updated for the two new categories
(`test_engine_sharing.py`, `test_doctor.py`, `test_cli.py`). `/code-review` (high effort) found the one
real bug before it shipped: a note found through more than one grounded passage
(`grounding_index.PASSAGES_PER_NOTE`) had its connections computed and attached twice, so its "Connected
to" line would have been duplicated in the prompt and its withheld count doubled; fixed by computing a
note's connections once per turn and sharing the same list across its passages, and pinned with a
revert-checked test. The same pass found and removed a dead, duplicated `_title_of` helper in
`vault_map.py` (the real one lives in `connections.py`, which uses it), a redundant case-insensitive
folder-name lookup in `vault_map._purpose_of` (the folder name there already comes from a real note's own
path, always exact), and a magic `"sympose"` string in `connections.py` that now imports
`reference.SOURCE` instead of repeating it a third time.

## Not built yet

- Meaning-based (embedding) connections, and how they would be ranked against the mechanical ones once both exist.
- Layer 4: an on-demand, model-requested count over the whole vault (#21, the round-trip dial).
- #80's tree/graph knob to hide folders and notes from view (a display question, not a grounding one; this record's position is that it should not change what the map or the connections contain).
- The web app's own version of the map or connections, which waits on #29's chat panel existing at all.
- The exact map-size ceiling and connection ranking above are proposals to measure, not final numbers; both are to be confirmed or corrected against the real vaults before the feature ships, the same way ADR 033's template share and ADR 034's title-matching rule were.
