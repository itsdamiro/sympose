import * as React from "react"

import { type PrefSpec, useCookiePreferences } from "@/lib/cookie-preferences"

/** `"sympose"` — the fixed product wordmark (default). `"vault"` — the
 *  active vault's name, truncated when it's long. */
export type BrandMarkLabel = "sympose" | "vault"

const SPEC: PrefSpec<{ label: BrandMarkLabel }> = {
  label: { cookie: "sympose:brand_mark_label", kind: "enum", default: "sympose", values: ["sympose", "vault"] },
}

/**
 * What the brand-mark wordmark shows, next to the workspace-switcher trigger
 * in `<TopBar>` and `<MainMenu>`. Cookie-backed per-browser view preference,
 * same convention as the editor / notification / nebula knobs — not backend
 * config, since it's purely how this browser likes the chrome to read.
 */
export function useBrandMarkLabel(): readonly [
  BrandMarkLabel,
  (value: BrandMarkLabel) => void,
] {
  const [prefs, set] = useCookiePreferences(SPEC)
  const setLabel = React.useCallback((value: BrandMarkLabel) => set("label", value), [set])
  return [prefs.label, setLabel] as const
}
