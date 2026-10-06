import { ControlRow, ControlSection } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { SharingState } from "@/lib/sharing-api"

/**
 * Settings → Cloud models (docs/decisions/031, 044): what a cloud model may receive from the user's vault, the
 * same switches as the notice above the message box and the terminal's `/share`, kept in the one `cloud_share`
 * list. Always reachable from here, whichever model is in use and whether or not the notice is closed. Takes
 * the chat's own sharing state, not a copy, so a switch here and the notice always agree. Everything starts off.
 */
function CloudSharingSection({
  state,
  onChange,
  noticeOpen,
  onNoticeOpenChange,
}: {
  state: SharingState | null
  onChange: (category: string, shared: boolean) => void
  /** The notice above the message box is shown (while the model is a cloud one). */
  noticeOpen: boolean
  onNoticeOpenChange: (open: boolean) => void
}) {
  return (
    <ControlSection title="Cloud models">
      <p className="text-xs text-fg-muted">
        A cloud model always receives your messages and the conversation. From your vault it may receive only what is
        switched on here; everything starts off. A model on your own computer receives all of it, and nothing leaves.
      </p>
      {state === null ? (
        <p className="text-sm text-fg-muted">Couldn&apos;t load these. Sympose isn't responding. Check that it's still running, then try again.</p>
      ) : (
        <>
          {state.categories.map((c) => (
            <div key={c.name} className="flex flex-col gap-1">
              <ControlRow label={c.name}>
                <SegmentedControl
                  size="sm"
                  aria-label={`Share ${c.name} with cloud models`}
                  value={c.shared ? "on" : "off"}
                  onValueChange={(v) => onChange(c.name, v === "on")}
                  options={[
                    { value: "on", label: "On" },
                    { value: "off", label: "Off" },
                  ]}
                />
              </ControlRow>
              <p className="text-xs text-fg-muted">{c.description}</p>
            </div>
          ))}
          <ControlRow label="Notice above the message box">
            <SegmentedControl
              size="sm"
              aria-label="Notice above the message box"
              value={noticeOpen ? "shown" : "hidden"}
              onValueChange={(v) => onNoticeOpenChange(v === "shown")}
              options={[
                { value: "shown", label: "Shown" },
                { value: "hidden", label: "Hidden" },
              ]}
            />
          </ControlRow>
          <p className="text-xs text-fg-muted">
            {state.cloud
              ? `The model in use (${state.model}) is a cloud model, so the notice is shown while it is on.`
              : `The model in use (${state.model}) is on your computer, so nothing leaves it and the notice is not shown.`}
          </p>
        </>
      )}
    </ControlSection>
  )
}

export { CloudSharingSection }
