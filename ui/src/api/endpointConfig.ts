import type { EndpointConfigEntry } from './models'

export const endpointConfig = {
  user: {
    authentication: {
      signIn: { service: 'user', url: '/authentication/sessions', verb: 'POST' },
      signUp: { service: 'user', url: '/authentication/users', verb: 'POST' },
      verify: { service: 'user', url: '/authentication/sessions/current', verb: 'GET' },
      signOut: { service: 'user', url: '/authentication/sessions/current', verb: 'DELETE' },
      getCurrentUser: { service: 'user', url: '/authentication/users/current', verb: 'GET' },
      updateCurrentUser: { service: 'user', url: '/authentication/users/current', verb: 'PATCH' },
    },
  },
  supplier: {
    suppliers: {
      list: { service: 'supplier', url: '/suppliers', verb: 'GET' },
      create: { service: 'supplier', url: '/suppliers', verb: 'POST' },
      update: {
        service: 'supplier',
        url: '/suppliers/:id',
        verb: 'PATCH',
        fieldMap: { id: 'path' },
      },
      remove: {
        service: 'supplier',
        url: '/suppliers/:id',
        verb: 'DELETE',
        fieldMap: { id: 'path' },
      },
    },
  },
  order: {},
  credit: {},
} as const satisfies Record<string, Record<string, Record<string, EndpointConfigEntry>>>
