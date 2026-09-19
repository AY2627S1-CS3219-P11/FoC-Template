import { useCallback, useMemo, useState, type PropsWithChildren } from 'react'
import type { ActiveRole, CurrentUserProfile, UserContextValue } from './models'
import { UserContext } from './UserContext'

const ACTIVE_ROLE_STORAGE_KEY = 'campus-errands-active-role-v1'

const getInitialRole = (): ActiveRole => {
  try {
    const storedRole = window.localStorage.getItem(ACTIVE_ROLE_STORAGE_KEY)
    return storedRole === 'courier' ? 'courier' : 'requester'
  } catch {
    return 'requester'
  }
}

type UserProviderProps = PropsWithChildren<{
  initialProfile: CurrentUserProfile
}>

export const UserProvider = ({ children, initialProfile }: UserProviderProps) => {
  const [profile, setProfile] = useState(initialProfile)
  const [activeRole, setActiveRoleState] = useState<ActiveRole>(getInitialRole)

  const setActiveRole = useCallback((role: ActiveRole) => {
    setActiveRoleState(role)
    try {
      window.localStorage.setItem(ACTIVE_ROLE_STORAGE_KEY, role)
    } catch {
      return
    }
  }, [])

  const value = useMemo<UserContextValue>(() => ({
    profile,
    activeRole,
    setActiveRole,
    setProfile,
  }), [activeRole, profile, setActiveRole])

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}
