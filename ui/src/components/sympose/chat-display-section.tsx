import { ControlRow, ControlSection } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { ChatDisplayPreferences } from "@/lib/use-chat-display-preferences"

/**
 * Settings → Chat: how the web chat draws things (docs/decisions/044). Cookie-backed through
 * `useChatDisplayPreferences`, like the editor and notification sections, and separate from the engine
 * settings: these change only what this page shows, never what the persona is sent or does.
 */
function ChatDisplaySection({
  prefs,
  setPref,
}: {
  prefs: ChatDisplayPreferences
  setPref: <K extends keyof ChatDisplayPreferences>(key: K, value: ChatDisplayPreferences[K]) => void
}) {
  return (
    <ControlSection title="Chat">
      <ControlRow label="Notes a reply was based on">
        <SegmentedControl
          size="sm"
          aria-label="Notes a reply was based on"
          value={prefs.showGrounding ? "on" : "off"}
          onValueChange={(v) => setPref("showGrounding", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        The line under a reply that says what it drew on: notes, earlier conversations, what it looked up. Hiding it
        only hides the line; the persona still uses them.
      </p>
      <ControlRow label="What a cloud reply was sent">
        <SegmentedControl
          size="sm"
          aria-label="What a cloud reply was sent"
          value={prefs.showCloudSent ? "on" : "off"}
          onValueChange={(v) => setPref("showCloudSent", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        A small cloud icon at the end of the line under a reply from a cloud model. Hover, focus or tap it to see what
        was sent and what was held back. Hiding it only hides the icon; what a cloud model may receive is set in
        sharing.
      </p>
      <ControlRow label="Type the busy line out by letters">
        <SegmentedControl
          size="sm"
          aria-label="Type the busy line out by letters"
          value={prefs.typeStatus ? "on" : "off"}
          onValueChange={(v) => setPref("typeStatus", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        The line above the message box while a reply is being written. Off shows each phrase at once; a browser set to
        reduce motion does that anyway.
      </p>
      <ControlRow label="Context meter">
        <SegmentedControl
          size="sm"
          aria-label="Context meter"
          value={prefs.showMeter ? "on" : "off"}
          onValueChange={(v) => setPref("showMeter", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        A ring and a percentage beside the message box: how much of the conversation the model can hold is in use. At
        100% your next message starts leaving the oldest turns out.
      </p>
    </ControlSection>
  )
}

export { ChatDisplaySection }
