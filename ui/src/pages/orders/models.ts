import type { Supplier } from '../suppliers/models'

export type OrderStatus = 'init' | 'open' | 'accepted' | 'picked_up' | 'delivered' | 'received' | 'completed' | 'cancelled' | 'expired' | 'rejected' | 'disputed'
export type OrderItem = { name: string; quantity: number }
export type Order = {
  id: string
  requester_id: string
  courier_id: string | null
  supplier_id: string
  supplier_snapshot: Supplier | null
  items: OrderItem[]
  pickup_notes: string | null
  credits: number
  status: OrderStatus
  credit_status: 'pending' | 'succeeded' | 'rejected'
  status_reason: string | null
  progress_due_at: string | null
  settlement_due_at: string | null
  created_at: string
  expires_at: string
  accepted_at: string | null
  updated_at: string
}
export type CreateOrderRequest = {
  supplier_id: string
  items: OrderItem[]
  pickup_notes: string | null
  credits: number
}
export type CreditBalance = { available_credits: number; reserved_credits: number }
export type OrderAction = 'accept' | 'cancel' | 'pickup' | 'deliver' | 'receive'

export const statusLabels: Record<OrderStatus, string> = {
  init: 'Reserving credits', open: 'Pending', accepted: 'Accepted', picked_up: 'Picked up',
  delivered: 'Delivered', received: 'Received', completed: 'Received',
  cancelled: 'Cancelled', expired: 'Expired', rejected: 'Credit reservation declined', disputed: 'Disputed',
}
export type OrderFilter = 'all' | 'disputed' | 'active' | 'finished'
export type OrderSort = 'attention' | 'newest' | 'oldest'
const activeStatuses: OrderStatus[] = ['init', 'open', 'accepted', 'picked_up', 'delivered', 'received']
export const filterPersonalOrders = (orders: Order[], filter: OrderFilter, sort: OrderSort) => {
  const attention = (order: Order) => order.status === 'disputed' ? 0 : activeStatuses.includes(order.status) ? 1 : 2
  return orders.filter((order) => filter === 'all' || (filter === 'disputed' ? order.status === 'disputed' : filter === 'active' ? activeStatuses.includes(order.status) : !activeStatuses.includes(order.status) && order.status !== 'disputed'))
    .sort((a, b) => (sort === 'attention' ? attention(a) - attention(b) : 0) || (sort === 'oldest' ? Date.parse(a.created_at) - Date.parse(b.created_at) : Date.parse(b.created_at) - Date.parse(a.created_at)) || a.id.localeCompare(b.id))
}

export const isUnaccepted = (order: Order) => order.status === 'open' || order.status === 'init'
export const canDispute = (order: Order) => ['accepted', 'picked_up', 'delivered'].includes(order.status) || (order.status === 'received' && order.credit_status === 'rejected')
export const remainingSeconds = (order: Order, now: number) => Math.max(0, Math.ceil((Date.parse(order.expires_at) - now) / 1000))

export const matchesOpenFilters = (order: Order, now: number, location: string, minCredits: string, maxCredits: string) => {
  const pickup = `${order.supplier_snapshot?.name ?? ''} ${order.supplier_snapshot?.building ?? ''}`.toLowerCase()
  return order.status === 'open' && remainingSeconds(order, now) > 0 && pickup.includes(location.trim().toLowerCase()) && (!minCredits || order.credits >= Number(minCredits)) && (!maxCredits || order.credits <= Number(maxCredits))
}
