export type ActiveRole = 'requester' | 'courier'

export type CurrentUserProfile = {
  username: string
  email: string
}

export type UserContextValue = {
  profile: CurrentUserProfile
  activeRole: ActiveRole
  setActiveRole: (role: ActiveRole) => void
  setProfile: (profile: CurrentUserProfile) => void
}
