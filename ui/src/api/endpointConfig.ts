import type { EndpointConfigEntry } from './models'

export const endpointConfig = {
  user: {
    authentication: {
      getCurrentUser: { service: 'user', url: '/authentication/users/current', verb: 'GET' },
      listManagedUsers: {
        service: 'user',
        url: '/authentication/users',
        verb: 'GET',
        fieldMap: { role: 'query', query: 'query', offset: 'query', limit: 'query' },
      },
      updateManagedUserRole: {
        service: 'user',
        url: '/authentication/users/:userId/role',
        verb: 'PATCH',
        fieldMap: { userId: 'path' },
      },
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
