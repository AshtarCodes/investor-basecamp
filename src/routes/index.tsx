import { createFileRoute, redirect } from '@tanstack/react-router'

import { Home } from '#/components/home.tsx'
import { authClient } from '#/lib/auth-client.ts'
import { getSession } from '#/lib/session.ts'

export const Route = createFileRoute('/')({
  beforeLoad: async () => {
    const session = await getSession()
    if (!session) throw redirect({ to: '/sign-in' })
    return { user: session.user }
  },
  component: HomeRoute,
})

function HomeRoute() {
  const { user } = Route.useRouteContext()
  const navigate = Route.useNavigate()

  return (
    <Home
      email={user.email}
      onSignOut={() => {
        void authClient.signOut().then(() => navigate({ to: '/sign-in' }))
      }}
    />
  )
}
