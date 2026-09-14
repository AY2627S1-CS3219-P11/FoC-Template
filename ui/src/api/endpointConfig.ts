import type { EndpointConfigEntry } from './models'

export const endpointConfig = {
  user: {
    authentication: {
      signIn: { url: '/authentication/sessions', verb: 'POST' },
      signUp: { url: '/authentication/users', verb: 'POST' },
      verify: { url: '/authentication/sessions/current', verb: 'GET' },
      signOut: { url: '/authentication/sessions/current', verb: 'DELETE' },
    },
  },
  supplier: {},
  order: {},
  credit: {},
} as const satisfies Record<string, Record<string, Record<string, EndpointConfigEntry>>>
