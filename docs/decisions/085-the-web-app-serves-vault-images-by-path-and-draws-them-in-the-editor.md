---
type: decision
status: accepted
date: 2026-10-16
projects: [sympose]
concepts: [Apps, Safe file handling]
amends: []
supersedes: []
tags: [type/decision, status/accepted, project/sympose, topic/web-app, topic/data-safety]
---

# 085 — The web app serves vault images by path and draws them in the editor

> **Summary.** One new read-only route serves one image file of the vault (PNG, JPEG, WebP, GIF, SVG), found by its path, and the editor draws `![[shot.png]]` and `![alt](path)` through it, so a note with screenshots reads as it does in Obsidian. It is a route of its own: an image never enters the tree, the graph, search, the persona's context or the vault map. Built (#129, 2026-10-16); the last section says where the build differs from the plan.

## Context

- A note that embeds a picture shows the reference as literal text in the web app. `ui/src/lib/resolve-embed.tsx` skips image embeds because the backend serves no vault file but notes (issue #129, checked in the running app on Stylo 0.24.0 on 2026-10-16: all four forms below showed as source).
- Stylo draws what the host returns. `embedSource(ref)` takes `![[ref]]` and `imageSource(src, alt)` (new in 0.24.0) takes `![alt](path)`; both are called with the text as written, may be async, and return `null` to keep the source literal. Stylo reads no size out of the alt text.
- ADR 047 settled that a note is found by its path from the vault's root and never by a same-named note elsewhere, because a stale path must not act on a different note. That is a rule about writes. A picture is only shown, so a wrong guess changes nothing on disk.
- `vault_defaults.IGNORE_FOLDERS` (`.obsidian`, `.git`, `Attachments`, `Drawings`, `.trash`) keeps those folders out of the tree and graph. `Attachments` is where Obsidian puts pasted images by default.
- The vault owner's word (2026-10-16): a file is found by its path, not just by its name; hiding a folder (ADR 037) is a display choice, so its images still show.

## Decision

**The route.** `GET` and `HEAD /api/vault/image?path=<ref>&from=<open note's path>&persona=<handle>` returns the file with its type, or 404. The web app asks `HEAD` first so a reference that matches no file stays literal, as today.

**Which file.** The reference is resolved in this order, and the first that exists wins:
1. a path from the vault's root (`assets/shot.png`, `Projects/x/logo.svg`);
2. a path from the folder of the open note (`from`), which is how most tools write `![alt](shot.png)`;
3. only for a reference with no folder in it (`shot.png`): a file of that name anywhere in what the persona can read, the shortest path winning and the alphabet breaking a tie. This is Obsidian's habit and ADR 047's reason does not apply to a picture; a reference with a folder in it is never searched for by name.

**What is served.** Only a file inside the folders the persona can read (`is_within_any`, symlinks resolved), by extension `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.svg`, compared in lower case; a path with a part that starts with a dot is refused; a file over 20 MB is refused (413). The vault owner did not set the size; 20 MB is a default that holds a large screenshot and stops a video renamed `.png`, and is one constant. A folder in `IGNORE_FOLDERS` (`Attachments`, `Drawings`) and a hidden folder (ADR 037) are not refused: they are not "where notes are".

**Headers.** `X-Content-Type-Options: nosniff` on every response; an SVG also carries `Content-Security-Policy: sandbox; default-src 'none'` so opening it directly runs no script, and the page only ever shows it through `<img>`. The type comes from the extension, never from the file.

**The editor.**
- `embedSource` already resolves a note; for a reference whose extension is an image type it returns `<img loading="lazy" src="/api/vault/image?...">` after the `HEAD` answers 200. A size hint after the pipe is honoured: `|300` is a width in pixels, `|300x200` a width and a height.
- `imageSource(src, alt)` returns the same `<img>` for a local path. An alt ending in `|300` or `|300x200` is read as a size and stripped from the alt text (Obsidian's `![alt|300](path)`). `http:`, `https:` and `data:` sources return `null` and stay literal: a note that loads any address on open is a tracking risk and no remote image is fetched.
- Both go through one function. Stylo's `imageAlign`, `imageWidth` and `invalidateImage` are not used.
- The note's own path (`from`) reaches the resolver through the ref `useLinkSources` already keeps (the editor reads these sources once, at mount, so the callback keeps its identity and reads the live note from a ref).

**What an image is not.** The tree, graph, search, related notes, the backlinks, the vault map, the persona's grounding and her tools keep reading notes only (`NOTE_EXTENSIONS`); no existing function gains an image case. A persona cannot open an image in this slice. Nothing is written, renamed or deleted.

## Consequences

- A note's screenshots, logos and diagrams show in the preview, split and in-place editor, with a size, from any folder including `Attachments`.
- The route is one more thing that reads files off disk, so it has the note routes' guard and a stricter type list; the tests have to cover the refusals, not only a picture that loads.
- A name shared by two files shows the shortest path's picture, silently; the vault owner can write the folder to pick the other.
- An image renamed or moved leaves its references showing as source; links are not rewritten (not part of this).
- Needs Stylo 0.24.0 (`imageSource`; 0.25.0 only adds type exports and is installed); the vendored build (`sympose/webui`) is rebuilt after the source change and committed on its own.

## Not part of this

Raw inline HTML or `<svg>` in a note, `data:` and remote images, pasting or uploading an image from inside Sympose, thumbnails, rewriting `![[…]]` and `![alt](…)` when an image is renamed, a lightbox, an image in the tree, and the persona reading an image.

## Test plan (before the code, so the slice can be checked)

- Route: a path from the root, a path from the note's folder, a bare name (shortest path wins, alphabetical tie), another persona's folder refused, `..` and an absolute path refused, a dot folder refused, a non-image type refused, a file over the limit refused, a missing file 404; `nosniff` on all, the sandbox policy on an SVG; `HEAD` gives the same status without a body; a hidden folder's image and an `Attachments` image are served.
- Not in the notes' world: the tree, graph and search of a vault holding images are unchanged.
- Resolver: an image embed with and without a size hint, a missing file stays literal, an alt size is read and stripped, `https:` and `data:` stay literal, a note embed still works.
- The real app, driven by a script on the scratch vault (`![[shot.png]]`, `![alt](assets/shot.png)`, a sized embed, a missing file) in headless Chrome, and a screenshot.

## Alternatives rejected

- **Resolve a bare name through the web app's tree.** The tree holds notes only, and adding files to it touches the persona (ADR 037 and the tree's own readers). Rejected; revisit if the walk the route does for a bare name is slow on a very large vault (it walks once per unresolved bare name; the "Built" section says what the browser does and does not reuse).
- **Apply "hiding a folder hides its images".** ADR 037 hides from the tree, search and graph; an image is none of those and a hidden folder is often exactly where the pictures are. Rejected on the owner's word.
- **Only an exact path, as ADR 047 does for notes.** Safer, but Obsidian users write `![[shot.png]]` and keep the file in `assets/`; their notes would stay unread. Rejected for a display-only route.

## Built (2026-10-16)

Same as decided, with these details the plan left open:

- **Refusals.** Everything the route does not serve (a missing file, a path outside the persona's folders, a dot folder, an absolute path, a type not on the list) is a plain 404, so the web app's `HEAD` leaves the reference as text and a refusal does not tell a path that exists from one that does not. Only a file over the limit says why (413). `sympose/vault_image.py` finds the file, `sympose/server_image_handlers.py` serves it.
- **Reading a reference.** A backslash is read as a slash, and `![alt](my%20shot.png)` and `![alt](<my shot.png>)` are asked for as `my shot.png`. An alt ending in `|300` or `|300x200` is read as a size and cut from the alt text; any other bar stays in the alt.
- **Where an image draws.** On its own line, and (Stylo 0.24.0, checked in real Chrome 2026-10-17 for both `![[…]]` and `![alt](…)`) inside a sentence, a list item, a quote or a heading. A table cell on the canvas, a linked image (`[![alt](src)](url)`) and code stay as source: Stylo's own limits. (Written on 2026-10-16 as "only an image on its own line draws": that was Stylo 0.23's rule, and 0.24.0 widened it.) An image inside an embedded note stays as source too: the nested preview has no sources of its own (the one-level depth cap of `resolve-embed.tsx`).
- **Code:** `ui/src/lib/resolve-image.tsx` (one function for both hooks), `vault-image-api.ts`, `useLinkSources` returns `imageSource` and takes the open note's path.
- **Checked** on a scratch vault in headless Chrome (a root path, `Attachments`, a bare name found in another folder, an SVG, `|100`, `|120x60`, `![sized|150](…)`; a missing file and an `https:` image stayed as source; no request went to the remote address). The backend tests (31) and the resolver tests cover the refusals the plan listed. Mutation check: 14 of 19 route mutants were caught at first; three survivors got tests (an absolute path, a folder-relative path, a backslash) and two give the same answer by design (a guard that only saves a walk, and skipping dot folders during the walk, which `_served` refuses anyway). Of 13 resolver mutants 12 were caught; the survivor was a style the browser applies by default, and it was removed.
- **Known cost, not changed:** a bare name walks the folders the persona can read, and the web app asks `HEAD` and then `GET`, so each such image costs two walks (the browser reuses the `GET`, not the `HEAD`). The plan said the answer is cached; only the picture is. It is the revisit the "Alternatives rejected" section named: if a very large vault is slow, cache the name index by the folders' modification times, or drop the `HEAD`.
- **After the review (2026-10-16).** A name is matched whatever its capital letters (Obsidian does the same; `![[Photo.PNG]]` finds `photo.png`), and a name that is not one of the image types is refused before any walk (the web app also stops asking about a source that does not end in an image extension). `useLinkSources` makes `embedSource` and `imageSource` depend on the open note's path instead of reading it from a ref set in an effect: an editor that remounts for another note asks in its own mount effect, before that ref was set, and drew a relative image from the previous note's folder.
- **The open note's path (`from`)** is the note or draft the editor shows; a persona's own file gets none, because it is not a vault path.
- **`imageAlign` and `imageWidth` (Stylo 0.24.0) are not used (2026-10-17).** Tried in the editor panel with a 1,600-pixel picture: the panel is about 470 pixels wide, so `wide` gains about 48 pixels and the picture runs into the gutters, and `center` puts a small picture in the middle against left-aligned text. The defaults (`left`, `column`) stay.
