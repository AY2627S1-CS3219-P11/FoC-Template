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
}

export type UpdateManagedUserRoleRequest = {
  userId: string
  role: ManagedUserRole
}
