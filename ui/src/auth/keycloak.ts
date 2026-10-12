import Keycloak from 'keycloak-js'
import type { CurrentSession, UserRole } from '../components/user/models'
import { CampusErrandsAPIError } from '../api/models'

export const usesKeycloak = import.meta.env.VITE_AUTH_PROVIDER === 'keycloak'

const keycloak = usesKeycloak ? new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL,
  realm: import.meta.env.VITE_KEYCLOAK_REALM,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
}) : null

let initialization: Promise<boolean> | undefined
const loginRequiredKey = 'campus-errands-login-required'

export const clearAuthentication = (): void => {
  keycloak?.clearToken()
  // Persist only this flag, never tokens. Do not automatically reacquire a
  // rejected session through SSO and redirect back to the protected route.
  window.sessionStorage.setItem(loginRequiredKey, 'true')
}

export const initializeAuthentication = async (): Promise<boolean> => {
  if (!keycloak) return false
  initialization ??= keycloak.init({
    onLoad: window.sessionStorage.getItem(loginRequiredKey) ? undefined : 'check-sso',
    pkceMethod: 'S256', checkLoginIframe: false,
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    silentCheckSsoFallback: false,
  })
  return initialization
}

export const accessToken = async (): Promise<string> => {
  await initializeAuthentication()
  if (!keycloak?.authenticated) throw new CampusErrandsAPIError('Please sign in.', 401)
  try {
    await keycloak.updateToken(30)
  } catch {
    clearAuthentication()
    throw new CampusErrandsAPIError('Your session has expired. Please sign in.', 401)
  }
  if (!keycloak.token) throw new CampusErrandsAPIError('Please sign in.', 401)
  return keycloak.token
}

export const currentSession = async (): Promise<CurrentSession> => {
  await accessToken()
  const claims = keycloak!.tokenParsed
  const roles = claims?.realm_access?.roles ?? []
  const role = (['admin_manager', 'admin', 'user'] as UserRole[]).find((candidate) => roles.includes(candidate))
  if (!claims?.sub || !role) throw new CampusErrandsAPIError('Your account has no application access.', 403)
  return { user_id: claims.sub, role }
}

export const login = async (returnTo = '/home'): Promise<void> => {
  await initializeAuthentication()
  const target = new URL(returnTo, window.location.origin)
  if (target.origin !== window.location.origin) throw new Error('Invalid return URL')
  window.sessionStorage.removeItem(loginRequiredKey)
  await keycloak!.login({ redirectUri: target.href })
}

export const logout = async (): Promise<void> => {
  await initializeAuthentication()
  await keycloak!.logout({ redirectUri: `${window.location.origin}/` })
}
