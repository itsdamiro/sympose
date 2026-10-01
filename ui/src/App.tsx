import { Toaster } from "@/components/ui/sonner"
import { ConfirmHost } from "@/lib/confirm"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { AppShell } from "@/routes/app-shell"

export function App() {
  const [notify] = useNotificationPreferences()
  return (
    <>
      <AppShell />
      <Toaster position={notify.position} />
      <ConfirmHost />
    </>
  )
}

export default App
