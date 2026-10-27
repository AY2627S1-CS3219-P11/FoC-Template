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
      listManagedUsers: {
        service: 'user',
        url: '/authentication/users',
        verb: 'GET',
        fieldMap: { role: 'query', query: 'query' },
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
  order: {
    orders: {
      disputed: { service: 'order', url: '/orders/admin/disputed', verb: 'GET' },
      resolve: { service: 'order', url: '/orders/admin/disputed/:id/resolve', verb: 'PATCH', fieldMap: { id: 'path' } },
      review: { service: 'order', url: '/orders/admin/disputed/:id/review', verb: 'GET', fieldMap: { id: 'path' } },
      repair: { service: 'order', url: '/orders/admin/disputed/:id/repair', verb: 'POST', fieldMap: { id: 'path' } },
      open: { service: 'order', url: '/orders/open', verb: 'GET' },
      requested: { service: 'order', url: '/orders/me/requested', verb: 'GET' },
      assigned: { service: 'order', url: '/orders/me/assigned', verb: 'GET' },
      create: { service: 'order', url: '/orders', verb: 'POST' },
      dispute: { service: 'order', url: '/orders/:id/dispute', verb: 'PATCH', fieldMap: { id: 'path' } },
      update: { service: 'order', url: '/orders/:id/:action', verb: 'PATCH', fieldMap: { id: 'path', action: 'path' } },
    },
  },
  credit: {
    credits: {
      current: { service: 'credit', url: '/credits/current', verb: 'GET' },
      auditLogs: { service: 'credit', url: '/credits/credit-audit-logs', verb: 'GET' },
    },
  },
} as const satisfies Record<string, Record<string, Record<string, EndpointConfigEntry>>>
