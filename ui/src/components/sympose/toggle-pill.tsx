import * as React from "react"

import { cn } from "@/lib/utils"

/** The small switch the app uses for a choice that is on or off, one to a name: outlined and tinted in the brand
 *  colour when on (the cloud notice's categories, the folders on a persona's request). */
function TogglePill({ pressed, className, ...props }: { pressed: boolean } & Omit<React.ComponentProps<"button">, "aria-pressed">) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      className={cn(
        "rounded-full border px-2.5 py-0.5 transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
        pressed ? "border-brand bg-brand/10 text-foreground" : "border-border text-fg-muted hover:bg-accent hover:text-foreground",
        className
      )}
      {...props}
    />
  )
}

export { TogglePill }
