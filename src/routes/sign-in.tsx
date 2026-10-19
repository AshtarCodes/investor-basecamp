import { createFileRoute } from '@tanstack/react-router'

import { SignInForm } from '#/components/sign-in-form.tsx'
import { submitCredentials } from '#/lib/credentials.ts'

export const Route = createFileRoute('/sign-in')({ component: SignInRoute })

function SignInRoute() {
  const navigate = Route.useNavigate()

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <SignInForm
        onSubmit={async (mode, credentials) => {
          const error = await submitCredentials(mode, credentials)
          if (!error) await navigate({ to: '/' })
          return error
        }}
      />
    </main>
  )
}
