import { useMemo, useState, type PropsWithChildren } from 'react'
import type { CurrentSession, CurrentUserProfile, UserContextValue } from './models'
import { UserContext } from './UserContext'

type UserProviderProps = PropsWithChildren<{
  session: CurrentSession
  initialProfile: CurrentUserProfile
}>

export const UserProvider = ({ children, initialProfile, session }: UserProviderProps) => {
  const [profile, setProfile] = useState(initialProfile)
  const value = useMemo<UserContextValue>(() => ({
    session,
    profile,
    setProfile,
  }), [profile, session])

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>
}
