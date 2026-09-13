import { useMemo } from 'react'
import { makeAuthenticatedCampusErrandsAPIRequest, makeCampusErrandsAPIRequest } from './api'
import type { AuthenticatedRequestOptions, RequestOptions } from './api'
import { endpointConfig } from './endpointConfig'
import type { SignInRequest, SignInResponse, SignOutResponse } from '../pages/authentication/models'

export const useCampusErrandsAPI = () => useMemo(() => ({
  request: makeCampusErrandsAPIRequest,
  authenticatedRequest: makeAuthenticatedCampusErrandsAPIRequest,
  authentication: {
    signIn: (request: SignInRequest, options?: RequestOptions) =>
      makeCampusErrandsAPIRequest<SignInRequest, SignInResponse>(
        request, endpointConfig.authentication.signIn, options,
      ),
    verify: (options?: AuthenticatedRequestOptions) =>
      makeAuthenticatedCampusErrandsAPIRequest<null, unknown>(null, endpointConfig.authentication.verify, options),
    signOut: (options?: RequestOptions) =>
      makeCampusErrandsAPIRequest<null, SignOutResponse>(null, endpointConfig.authentication.signOut, options),
  },
}), [])
