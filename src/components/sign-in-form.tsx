import { useState, type FormEvent } from 'react'

import { Button } from '#/components/ui/button.tsx'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '#/components/ui/card.tsx'
import { Input } from '#/components/ui/input.tsx'
import { Label } from '#/components/ui/label.tsx'
import type { Credentials, CredentialsMode } from '#/lib/credentials.ts'

interface SignInFormProps {
  onSubmit: (
    mode: CredentialsMode,
    credentials: Credentials,
  ) => Promise<string | undefined>
}

export function SignInForm({ onSubmit }: SignInFormProps) {
  const [mode, setMode] = useState<CredentialsMode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string>()
  const [pending, setPending] = useState(false)
  const signingIn = mode === 'sign-in'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(await onSubmit(mode, { email, password }))
    setPending(false)
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle>{signingIn ? 'Sign in' : 'Create account'}</CardTitle>
        <CardDescription>Investor Basecamp</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={signingIn ? 'current-password' : 'new-password'}
              minLength={8}
              required
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          )}
        </CardContent>
        <CardFooter className="mt-6 flex flex-col gap-2">
          <Button type="submit" className="w-full" disabled={pending}>
            {signingIn ? 'Sign in' : 'Create account'}
          </Button>
          <Button
            type="button"
            variant="link"
            onClick={() => {
              setMode(signingIn ? 'sign-up' : 'sign-in')
              setError(undefined)
            }}
          >
            {signingIn ? 'Need an account? Create one' : 'Have an account? Sign in'}
          </Button>
        </CardFooter>
      </form>
    </Card>
  )
}
