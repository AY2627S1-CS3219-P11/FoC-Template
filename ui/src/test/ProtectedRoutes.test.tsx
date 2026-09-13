import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ProtectedRoutes from '../components/protectedRoutes/ProtectedRoutes'

let container: HTMLDivElement
let root: Root
let router: ReturnType<typeof createMemoryRouter>

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
  router = createMemoryRouter([
    { path: '/', element: <p>Sign in</p> },
    { element: <ProtectedRoutes />, children: [{ path: '/home', element: <p>Private content</p> }] },
  ], { initialEntries: ['/home?tab=active#list'] })
})

afterEach(async () => {
  await act(async () => root.unmount())
  router.dispose()
  container.remove()
  vi.unstubAllGlobals()
})

it('keeps private content hidden until verification succeeds', async () => {
  let resolve!: (response: Response) => void
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((done) => { resolve = done })))
  await act(async () => root.render(<RouterProvider router={router} />))
  expect(container.textContent).toContain('Checking your session')
  expect(container.textContent).not.toContain('Private content')
  await act(async () => resolve(Response.json({ id: 'user-1' })))
  expect(container.textContent).toBe('Private content')
})

it('redirects an unauthenticated session and preserves the requested location', async () => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(Response.json({}, { status: 401 }))))
  await act(async () => root.render(<RouterProvider router={router} />))
  expect(container.textContent).toBe('Sign in')
  expect(router.state.location.state).toEqual({ returnTo: '/home?tab=active#list' })
})

it('shows a retry action for server errors without redirecting or revealing content', async () => {
  const fetch = vi.fn()
    .mockResolvedValueOnce(Response.json({}, { status: 503 }))
    .mockResolvedValueOnce(Response.json({ id: 'user-1' }))
  vi.stubGlobal('fetch', fetch)
  await act(async () => root.render(<RouterProvider router={router} />))
  expect(container.textContent).toContain('Unable to verify your session')
  expect(container.textContent).not.toContain('Private content')
  expect(router.state.location.pathname).toBe('/home')
  await act(async () => container.querySelector('button')!.click())
  expect(container.textContent).toBe('Private content')
})
