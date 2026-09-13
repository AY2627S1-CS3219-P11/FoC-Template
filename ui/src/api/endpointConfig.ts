import type { EndpointConfigEntry } from './models'

export const endpointConfig = {
  authentication: {
    signIn: { url: '/authentication/sessions', verb: 'POST' },
    verify: { url: '/authentication/sessions/current', verb: 'GET' },
    signOut: { url: '/authentication/sessions/current', verb: 'DELETE' },
  },
} as const satisfies Record<string, Record<string, EndpointConfigEntry>>
