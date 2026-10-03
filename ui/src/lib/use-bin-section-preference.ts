import { type PrefSpec, useCookiePreferences } from "@/lib/cookie-preferences"

/** Which half of the Bin is listed, kept in a cookie like the other interface preferences (docs/decisions/057, 060). */
export interface BinPreferences {
  section: "notes" | "conversations"
}

const SPEC: PrefSpec<BinPreferences> = {
  section: { cookie: "sympose:bin.section", kind: "enum", default: "notes", values: ["notes", "conversations"] },
}

export function useBinPreferences() {
  return useCookiePreferences(SPEC)
}
