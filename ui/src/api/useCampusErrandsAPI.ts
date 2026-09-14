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
        makeAuthenticatedCampusErrandsAPIRequest<null, unknown>(
          null, endpointConfig.user.authentication.verify, options,
        ),
      signOut: () =>
        makeCampusErrandsAPIRequest<null, SignOutResponse>(
          null, endpointConfig.user.authentication.signOut,
        ),
    },
  },
  supplier: {},
  order: {},
  credit: {},
}), [])
