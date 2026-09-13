import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { CampusErrandsAPIError } from '../../api/models'
import { useCampusErrandsAPI } from '../../api/useCampusErrandsAPI'
import { routes } from '../../routes'

type AuthenticationStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'error'

const ProtectedRoutes = () => {
  const [status, setStatus] = useState<AuthenticationStatus>('loading')
  const [attempt, setAttempt] = useState(0)
  const api = useCampusErrandsAPI()
  const location = useLocation()

  useEffect(() => {
    const controller = new AbortController()

    const verify = async () => {
      try {
        await api.authentication.verify({
          signal: controller.signal,
          onUnauthenticated: () => {},
        })
        if (!controller.signal.aborted) setStatus('authenticated')
      } catch (error) {
        if (controller.signal.aborted) return
        setStatus(error instanceof CampusErrandsAPIError && error.status === 401
          ? 'unauthenticated'
          : 'error')
      }
    }

    void verify()
    return () => controller.abort()
  }, [api.authentication, attempt])

  if (status === 'loading') return <p role="status">Checking your session…</p>
  if (status === 'error') {
    return (
      <div role="alert">
        <p>Unable to verify your session.</p>
        <button type="button" onClick={() => {
          setStatus('loading')
          setAttempt((value) => value + 1)
        }}>Try again</button>
      </div>
    )
  }
  if (status === 'unauthenticated') {
    const returnTo = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to={routes.signIn} state={{ returnTo }} replace />
  }
  return <Outlet />
}

export default ProtectedRoutes
