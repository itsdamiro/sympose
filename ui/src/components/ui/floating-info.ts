/**
 * The shape of every floating info surface (the tooltip, the popover): the panels' `--radius-lg` corner, the
 * menus' muted text weight, a soft shadow over a hairline ring, and the same open/close motion. The frosted
 * background is not here: it is the one `index.css` rule keyed off `data-slot` that every menu uses too, so a
 * hover or info popup can never look like a different app (docs/decisions/060). Spacing is the one thing that
 * differs from a menu: there are no rows, so the content gets its own padding.
 */
export const floatingInfoClass =
  "z-50 w-fit max-w-xs origin-(--transform-origin) rounded-lg px-3 py-2 text-xs text-muted-foreground shadow-2xl ring-1 ring-foreground/5 outline-none dark:ring-foreground/10 data-[side=bottom]:slide-in-from-top-2 data-[side=inline-end]:slide-in-from-left-2 data-[side=inline-start]:slide-in-from-right-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95"
