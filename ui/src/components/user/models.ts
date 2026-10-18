export type UserRole = 'user' | 'admin' | 'admin_manager'

export type CurrentSession = {
  user_id: string
  role: UserRole
}

export type CurrentUserProfile = {
  username: string
  email: string
}

export type UserContextValue = {
  session: CurrentSession
  profile: CurrentUserProfile
  setProfile: (profile: CurrentUserProfile) => void
}
