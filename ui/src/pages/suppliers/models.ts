export type UserRole = 'user' | 'admin' | 'admin_manager'

export type CurrentSession = {
  user_id: string
  role: UserRole
}

export type SupplierCategory = 'Food' | 'Shopping' | 'Printing' | 'Food/Coffee'

export type Supplier = {
  id: string
  name: string
  category: SupplierCategory
  building: string
  floor: number
  description: string
  lattitude: number
  longitude: number
  startingTime: string
  closingTime: string
  imageUrl: string | null
}

export type SupplierCreateRequest = Omit<Supplier, 'id'>
export type SupplierUpdateRequest = Partial<SupplierCreateRequest> & { id: string }
