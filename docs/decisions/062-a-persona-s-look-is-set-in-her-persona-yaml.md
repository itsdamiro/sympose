# 062 — A persona's look is set in her persona.yaml

> **Status: Accepted (2026-10-03), designed with damiro. The icon and the colour are built; the banner, the profile picture and the choice of icon set are designed here and built later.** Builds on ADR 011 (a persona's directory), ADR 046 (the tracked persona files are defaults the app never writes) and ADR 060 (the web chat's chrome).

## Context

A persona's identity in the web app (her icon and her colour, on her avatar, her reply headers, the menu row, the switcher, the Persona page's band and the empty chat) came from a table in the web app's source: Samantha's were written there, and every other persona got the same neutral brain icon in grey. A persona a user creates therefore had no look of her own, although her look is most of her brand, and a look kept in the app's source cannot travel with the persona's folder or be set by the user.

## Decision

**The persona's own file is where her look lives.** `persona.yaml` takes optional keys: `icon` (the name of her icon), `accent` (her colour in light mode) and `accent_dark` (in dark mode; the light colour is used for both when it is missing). The roster (`GET /api/personas`) returns them, and the web app draws her from them wherever it draws her. Anything missing falls back to what the app already did: Samantha's shipped look, or the neutral one. Samantha's own `persona.yaml` now carries hers, so the shipped default is data, like any other persona's.

**The icon is a name in an icon set, and the set is the user's choice.** The app ships one set (the one it already uses) and a persona names her icon in it (`icon: leaf`). Which set the app draws from is meant to be a theme setting of the user's (later), so a persona picks her icon from the set in use and a name the set does not have falls back to the default icon instead of breaking. A persona file is therefore not tied to one set's drawings, only to names.

**What the backend checks.** `icon` must be a short lower-case name and a colour a short string of colour characters (a hex, `rgb(...)`, `oklch(...)`); anything of another shape is ignored, not passed on, because the value ends up in the page (an icon's name, a colour in a style attribute). A persona never loses her place over a bad look value.

**Reserved for the same file, not built.** `banner` (the band across the top of her page, today her accent colour) and `picture` (her profile picture in place of the icon) belong in `persona.yaml` too, as paths to image files in her folder. They are named here so the file's shape is settled; the web app does not read them yet.

**Choosing, later.** Choosing the icon and the colour in the app belongs to the theme settings, where the icon set is chosen, and writes the user's pick the way a model pick is written: a local override beside the shipped file (ADR 046), never the tracked file. Until then the look is set by editing `persona.yaml`.

## Consequences

- A persona the user creates can have her own icon and colour by adding three lines to her file, and it shows in every place she is drawn, light and dark.
- The look is read from the roster once and remembered by the web app (`setLiveLooks`), so the many places that draw her need no new props; a persona not yet in the roster (offline) keeps the old defaults.
- The icon list is curated (about forty names), so a persona cannot ask for an arbitrary drawing and the set stays one visual family.

## Alternatives rejected

- **A colour and icon table in the app's source for every persona.** It cannot know a user's personas and cannot travel with a persona's folder.
- **Any icon name from the library.** The whole library is thousands of drawings in mixed styles, and loading it all costs the app's size; a curated set is one family and small.
- **The icon as an image file only.** It does not recolour for light and dark and needs file handling; it is the later `picture`, beside the icon, not instead of it.
