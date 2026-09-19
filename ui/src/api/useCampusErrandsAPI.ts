import { useMemo } from 'react'
import { makeAuthenticatedCampusErrandsAPIRequest, makeCampusErrandsAPIRequest } from './api'
import type { AuthenticatedRequestOptions } from './api'
import { endpointConfig } from './endpointConfig'
import type {
  SignInRequest,
  SignInResponse,
  SignOutResponse,
  SignUpRequest,
  SignUpResponse,
} from '../pages/authentication/models'
import type {
  CurrentSession,
  Supplier,
  SupplierCreateRequest,
  SupplierUpdateRequest,
} from '../pages/suppliers/models'
import type { CurrentUserProfile } from '../components/user/models'
import type { UpdateCurrentUserProfileRequest } from '../pages/profile/models'

export const useCampusErrandsAPI = () => useMemo(() => ({
  request: makeCampusErrandsAPIRequest,
  authenticatedRequest: makeAuthenticatedCampusErrandsAPIRequest,
  user: {
    authentication: {
      signIn: (request: SignInRequest) =>
        makeCampusErrandsAPIRequest<SignInRequest, SignInResponse>(
          request, endpointConfig.user.authentication.signIn,
        ),
      signUp: (request: SignUpRequest) =>
        makeCampusErrandsAPIRequest<SignUpRequest, SignUpResponse>(
          request, endpointConfig.user.authentication.signUp,
        ),
      verify: (options?: AuthenticatedRequestOptions) =>
        makeAuthenticatedCampusErrandsAPIRequest<null, CurrentSession>(
          null, endpointConfig.user.authentication.verify, options,
        ),
      signOut: () =>
        makeCampusErrandsAPIRequest<null, SignOutResponse>(
          null, endpointConfig.user.authentication.signOut,
        ),
      getCurrentUser: (options?: AuthenticatedRequestOptions) =>
        makeAuthenticatedCampusErrandsAPIRequest<null, CurrentUserProfile>(
          null, endpointConfig.user.authentication.getCurrentUser, options,
        ),
      updateCurrentUser: (request: UpdateCurrentUserProfileRequest) =>
        makeAuthenticatedCampusErrandsAPIRequest<UpdateCurrentUserProfileRequest, CurrentUserProfile>(
          request, endpointConfig.user.authentication.updateCurrentUser,
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
