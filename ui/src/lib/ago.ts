/** "3d ago" / "2h ago" / "just now" from an epoch-seconds timestamp. */
export function ago(epochSeconds: number): string {
  const secs = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds))
  if (secs < 60) return "just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

/** `ago` for an ISO timestamp (a conversation's `updated_at`); empty when there is none or it cannot be read. */
export function agoIso(stamp: string | null): string {
  const at = stamp ? Date.parse(stamp) : NaN
  return Number.isNaN(at) ? "" : ago(at / 1000)
}
