import { useMemo } from 'react'
import { currentSession, logout } from '../auth/keycloak'
import { makeAuthenticatedCampusErrandsAPIRequest, makeCampusErrandsAPIRequest } from './api'
import type { AuthenticatedRequestOptions } from './api'
import { endpointConfig } from './endpointConfig'
import type {
  Supplier,
  SupplierCreateRequest,
  SupplierUpdateRequest,
} from '../pages/suppliers/models'
import type { CurrentUserProfile } from '../components/user/models'
import type {
  ListManagedUsersRequest,
  ManagedUser,
  ManagedUserPage,
  UpdateManagedUserRoleRequest,
} from '../pages/adminManagerPortal/models'

export const useCampusErrandsAPI = () => useMemo(() => ({
  request: makeCampusErrandsAPIRequest,
  authenticatedRequest: makeAuthenticatedCampusErrandsAPIRequest,
  user: {
    authentication: {
      verify: currentSession,
      signOut: logout,
      getCurrentUser: (options?: AuthenticatedRequestOptions) =>
        makeAuthenticatedCampusErrandsAPIRequest<null, CurrentUserProfile>(
          null, endpointConfig.user.authentication.getCurrentUser, options,
        ),
      listManagedUsers: (request: ListManagedUsersRequest) =>
        makeAuthenticatedCampusErrandsAPIRequest<ListManagedUsersRequest, ManagedUserPage>(
          request, endpointConfig.user.authentication.listManagedUsers,
        ),
      updateManagedUserRole: (request: UpdateManagedUserRoleRequest) =>
        makeAuthenticatedCampusErrandsAPIRequest<UpdateManagedUserRoleRequest, ManagedUser>(
          request, endpointConfig.user.authentication.updateManagedUserRole,
        ),
    },
  },
  supplier: {
    list: (options?: AuthenticatedRequestOptions) =>
      makeAuthenticatedCampusErrandsAPIRequest<null, Supplier[]>(
        null, endpointConfig.supplier.suppliers.list, options,
      ),
    create: (request: SupplierCreateRequest) =>
      makeAuthenticatedCampusErrandsAPIRequest<SupplierCreateRequest, Supplier>(
        request, endpointConfig.supplier.suppliers.create,
      ),
    update: (request: SupplierUpdateRequest) =>
      makeAuthenticatedCampusErrandsAPIRequest<SupplierUpdateRequest, Supplier>(
        request, endpointConfig.supplier.suppliers.update,
      ),
    remove: (id: string) =>
      makeAuthenticatedCampusErrandsAPIRequest<{ id: string }, null>(
        { id }, endpointConfig.supplier.suppliers.remove,
      ),
  },
  order: {},
  credit: {},
}), [])
