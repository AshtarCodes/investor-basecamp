import { Button } from '#/components/ui/button.tsx'

interface HomeProps {
  email: string
  onSignOut: () => void
}

export function Home({ email, onSignOut }: HomeProps) {
  return (
    <main className="mx-auto flex max-w-3xl items-center justify-between p-8">
      <h1 className="text-2xl font-semibold">Investor Basecamp</h1>
      <div className="flex items-center gap-4 text-sm">
        <span>Signed in as {email}</span>
        <Button variant="outline" size="sm" onClick={onSignOut}>
          Sign out
        </Button>
      </div>
    </main>
  )
}
