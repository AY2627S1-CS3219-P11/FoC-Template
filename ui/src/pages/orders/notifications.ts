import type { Order } from './models'

export type OrderNotice = { id: string; title: string; message: string; order: Order }

// Only announce observed changes, not historical orders on initial load.
export const orderNotice = (previous: Order | undefined, order: Order, userId: string): OrderNotice | null => {
  if (!previous) return null
  if (previous.status === 'init' && order.status === 'open' && order.requester_id === userId) {
    return { id: `${order.id}:open`, title: 'Your request is up!', message: `${order.credits} credits have been reserved. They will only be taken once your order is completed.`, order }
  }
  if (previous.status !== 'completed' && order.status === 'completed' && order.credit_status === 'succeeded' && order.courier_id === userId) {
    return { id: `${order.id}:completed`, title: 'Credits received!', message: `Your delivery is complete. ${order.credits} credits have been added to your available balance.`, order }
  }
  return null
}
