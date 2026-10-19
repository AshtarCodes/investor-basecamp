import { authClient } from '#/lib/auth-client.ts'

export type CredentialsMode = 'sign-in' | 'sign-up'

export interface Credentials {
  email: string
  password: string
}

export async function submitCredentials(
  mode: CredentialsMode,
  { email, password }: Credentials,
): Promise<string | undefined> {
  const { error } =
    mode === 'sign-in'
      ? await authClient.signIn.email({ email, password })
      : await authClient.signUp.email({ email, password, name: email })
  if (!error) return undefined
  return error.message ?? 'Something went wrong. Try again.'
}
