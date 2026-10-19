import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { expect, test, vi } from 'vitest'

import { renderWithQuery } from '../../tests/render.tsx'
import { SignInForm } from './sign-in-form.tsx'

test('switching to sign-up submits the credentials in sign-up mode', async () => {
  const user = userEvent.setup()
  const onSubmit = vi
    .fn<ComponentProps<typeof SignInForm>['onSubmit']>()
    .mockResolvedValue(undefined)
  renderWithQuery(<SignInForm onSubmit={onSubmit} />)

  await user.click(screen.getByRole('button', { name: /create one/i }))
  await user.type(screen.getByLabelText('Email'), 'me@example.com')
  await user.type(screen.getByLabelText('Password'), 'correct-horse')
  await user.click(screen.getByRole('button', { name: 'Create account' }))

  expect(onSubmit).toHaveBeenCalledWith('sign-up', {
    email: 'me@example.com',
    password: 'correct-horse',
  })
})

test('shows the error the submit returns', async () => {
  const user = userEvent.setup()
  renderWithQuery(
    <SignInForm onSubmit={() => Promise.resolve('Invalid email or password')} />,
  )

  await user.type(screen.getByLabelText('Email'), 'me@example.com')
  await user.type(screen.getByLabelText('Password'), 'wrong-password')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Invalid email or password',
  )
})
