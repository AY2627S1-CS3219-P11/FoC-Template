export type ManagedUserRole = 'admin' | 'user'

export type ManagedUser = {
  user_id: string
  username: string
  email: string
  role: ManagedUserRole
}

export type ListManagedUsersRequest = {
  role: ManagedUserRole
  query?: string
  offset: number
  limit: number
}

export type ManagedUserPage = {
  items: ManagedUser[]
  offset: number
  limit: number
  has_more: boolean
}

export type UpdateManagedUserRoleRequest = {
  userId: string
  role: ManagedUserRole
}
