import { useMemo } from 'react'
import { makeAuthenticatedCampusErrandsAPIRequest, makeCampusErrandsAPIRequest } from './api'
import type { AuthenticatedRequestOptions, RequestOptions } from './api'
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
      signIn: (request: SignInRequest, options?: RequestOptions) =>
        makeCampusErrandsAPIRequest<SignInRequest, SignInResponse>(
          request, endpointConfig.user.authentication.signIn, options,
        ),
      signUp: (request: SignUpRequest, options?: RequestOptions) =>
        makeCampusErrandsAPIRequest<SignUpRequest, SignUpResponse>(
          request, endpointConfig.user.authentication.signUp, options,
        ),
      verify: (options?: AuthenticatedRequestOptions) =>
        makeAuthenticatedCampusErrandsAPIRequest<null, unknown>(
          null, endpointConfig.user.authentication.verify, options,
        ),
      signOut: (options?: RequestOptions) =>
        makeCampusErrandsAPIRequest<null, SignOutResponse>(
          null, endpointConfig.user.authentication.signOut, options,
        ),
    },
  },
  supplier: {},
  order: {},
  credit: {},
}), [])
