import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useCampusErrandsAPI } from '../../api/useCampusErrandsAPI'
import { useUser } from '../../components/user/UserContext'
import { useToast } from '../../components/toast/useToast'
import type { Supplier } from '../suppliers/models'
import { filterPersonalOrders, type OrderFilter, type OrderSort, canDispute, isUnaccepted, matchesOpenFilters, remainingSeconds, statusLabels, type Order, type OrderAction, type CreditBalance, type OrderItem } from './models'
import { Modal } from '../../components/modal/Modal'
import styles from './Orders.module.css'

type View = 'open' | 'requested' | 'assigned'
type Resource = View | 'credits' | 'suppliers'
type ResourceState = { loaded: boolean; error: boolean }
const initialResourceState: Record<Resource, ResourceState> = {
  open: { loaded: false, error: false },
  requested: { loaded: false, error: false },
  assigned: { loaded: false, error: false },
  credits: { loaded: false, error: false },
  suppliers: { loaded: false, error: false },
}
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.'

const Orders = () => {
  const api = useCampusErrandsAPI()
  const { session } = useUser()
  const { showErrorToast, showSuccessToast } = useToast()
  const [view, setView] = useState<View>('open')
  const [orders, setOrders] = useState<Record<View, Order[]>>({ open: [], requested: [], assigned: [] })
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [balance, setBalance] = useState<CreditBalance | null>(null)
  const [resources, setResources] = useState(initialResourceState)
  const [now, setNow] = useState(() => Date.now())
  const [formOpen, setFormOpen] = useState(false)
  const [supplierId, setSupplierId] = useState('')
  const [items, setItems] = useState<OrderItem[]>([{ name: '', quantity: 1 }])
  const [delivery, setDelivery] = useState('')
  const [notes, setNotes] = useState('')
  const [credits, setCredits] = useState('1')
  const [busy, setBusy] = useState<string | null>(null)
  const [reportOrder, setReportOrder] = useState<Order | null>(null)
  const [reason, setReason] = useState('')
  const [reportError, setReportError] = useState('')
  const [cancelOrder, setCancelOrder] = useState<Order | null>(null)
  const [statusFilter, setStatusFilter] = useState<OrderFilter>('all')
  const [sort, setSort] = useState<OrderSort>('attention')
  const [location, setLocation] = useState('')
  const [minCredits, setMinCredits] = useState('')
  const [maxCredits, setMaxCredits] = useState('')
  const refreshing = useRef(false)
  const mutationLock = useRef(false)
  const [creationAttempt, setCreationAttempt] = useState<{ payload: string; key: string } | null>(null)

  const refresh = useCallback(async () => {
    if (refreshing.current) return
    refreshing.current = true
    try {
      const loaders: Record<Resource, () => Promise<void>> = {
        open: async () => {
          const open = await api.order.open()
          setOrders((current) => ({ ...current, open }))
        },
        requested: async () => {
          const requested = await api.order.requested()
          setOrders((current) => ({ ...current, requested }))
        },
        assigned: async () => {
          const assigned = await api.order.assigned()
          setOrders((current) => ({ ...current, assigned }))
        },
        credits: async () => { setBalance(await api.credit.current()) },
        suppliers: async () => { setSuppliers(await api.supplier.list()) },
      }
      await Promise.all((Object.entries(loaders) as [Resource, () => Promise<void>][]).map(async ([key, load]) => {
        try {
          await load()
          setResources((current) => ({ ...current, [key]: { loaded: true, error: false } }))
        } catch {
          setResources((current) => ({ ...current, [key]: { ...current[key], error: true } }))
        }
      }))
    } finally {
      refreshing.current = false
    }
  }, [api])

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void refresh(), 0)
    const poll = window.setInterval(() => void refresh(), 5000)
    const clock = window.setInterval(() => setNow(Date.now()), 1000)
    return () => { window.clearTimeout(initialLoad); window.clearInterval(poll); window.clearInterval(clock) }
  }, [refresh])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const amount = Number(credits)
    const request = { supplier_id: supplierId, items: items.map((item) => ({ ...item, name: item.name.trim() })), pickup_notes: `Delivery location: ${delivery.trim()}${notes.trim() ? `\nPickup notes: ${notes.trim()}` : ''}`, credits: amount }
    const payload = JSON.stringify(request)
    const retry = creationAttempt?.payload === payload
    if (mutationLock.current) return
    if (resources.suppliers.error || resources.credits.error || resources.open.error) {
      showErrorToast('We can’t submit your request until suppliers, credits, and orders are available again. Your draft has been kept.')
      return
    }
    if ((!retry && !suppliers.some((supplier) => supplier.id === supplierId)) || !delivery.trim() || items.some((item) => !item.name.trim() || !Number.isSafeInteger(item.quantity) || item.quantity < 1) || !Number.isSafeInteger(amount) || amount < 1 || (!retry && (!balance || amount > balance.available_credits))) {
      showErrorToast('Choose an active supplier, complete the delivery details, and offer whole credits within your available balance.')
      return
    }
    mutationLock.current = true
    setBusy('create')
    try {
      const attempt = creationAttempt?.payload === payload ? creationAttempt : { payload, key: crypto.randomUUID() }
      setCreationAttempt(attempt)
      await api.order.create(request, attempt.key)
      setCreationAttempt(null)
      setFormOpen(false)
      setItems([{ name: '', quantity: 1 }]); setDelivery(''); setNotes(''); setCredits('1')
      setView('requested')
      showSuccessToast('Request submitted. It becomes available once credits are reserved.')
      await refresh()
    } catch (error) { showErrorToast(errorMessage(error)) }
    finally { mutationLock.current = false; setBusy(null) }
  }

  const update = async (order: Order, action: OrderAction) => {
    if (mutationLock.current) return
    mutationLock.current = true
    setBusy(order.id)
    try {
      await api.order.update(order.id, action)
      if (action === 'cancel') setCancelOrder(null)
      showSuccessToast(action === 'receive' ? 'Receipt confirmed. Credit transfer is processing.' : 'Order updated.')
    } catch (error) { showErrorToast(errorMessage(error)) }
    finally { await refresh(); mutationLock.current = false; setBusy(null) }
  }

  const dispute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (mutationLock.current || !reportOrder) return
    if (!reason.trim() || reason.trim().length > 2000) { setReportError('Enter a reason of 1–2,000 characters.'); return }
    mutationLock.current = true
    setBusy(reportOrder.id)
    setReportError('')
    try {
      const result = await api.order.dispute(reportOrder.id, reason.trim())
      setReportOrder(null)
      setReason('')
      showSuccessToast(result.status_reason === reason.trim() ? 'Order disputed.' : 'This order was already disputed. The original reason has been kept.')
    } catch (error) { setReportError(errorMessage(error)) }
    finally { await refresh(); mutationLock.current = false; setBusy(null) }
  }

  const loadError = resources[view].error
  const loadingOrders = !resources[view].loaded && !loadError
  const creationUnavailable = resources.suppliers.error || resources.credits.error || resources.open.error

  const visibleOrders = view === 'open'
    ? orders.open.filter((order) => matchesOpenFilters(order, now, location, minCredits, maxCredits))
    : filterPersonalOrders(orders[view], statusFilter, sort)

  return <main className={styles.page}>
    <header className={styles.heading}>
      <div><p className={styles.eyebrow}>A little help goes a long way</p><h1>Orders</h1><p>Ask for a pickup. Help along your route. You can do both, anytime.</p></div>
      <button className={styles.primary} onClick={() => setFormOpen(true)} aria-haspopup="dialog" aria-controls="new-request">+ New request</button>
    </header>
    <section className={styles.wallet} aria-label="Credit balance">
      <div><span>Available credits</span><strong>{resources.credits.error ? '—' : balance?.available_credits ?? '—'}</strong></div>
      <div><span>Reserved credits</span><strong>{resources.credits.error ? '—' : balance?.reserved_credits ?? '—'}</strong></div>
      {resources.credits.error
        ? <div className={styles.notice} role="status"><strong>Credit balance is temporarily unavailable</strong><p>You can still browse and manage orders. New requests need a current balance.</p><button onClick={() => void refresh()}>Try again</button></div>
        : !resources.credits.loaded ? <p role="status">Loading your credit balance…</p>
        : <p>Credits are reserved for your requests, returned on cancellation or expiry, and awarded to the courier after you confirm receipt.</p>}
    </section>
    {formOpen && <Modal id="new-request" labelledBy="request-title" onClose={() => setFormOpen(false)} busy={busy === 'create'}><section className={styles.formPanel}>
      <div className={styles.formHeading}><h2 id="request-title">What do you need picked up?</h2><button type="button" disabled={busy === 'create'} onClick={() => setFormOpen(false)}>Close</button></div>
      <p>Only active suppliers are available. Open requests expire after 15 minutes.</p>
      {resources.suppliers.error && <div className={styles.notice} role="status"><strong>Suppliers are temporarily unavailable</strong><p>Your draft is safe. Please try again before submitting a new request.</p><button onClick={() => void refresh()}>Try again</button></div>}
      {resources.credits.error && <div className={styles.notice} role="status"><p>We can’t check your credit balance right now. Please try again before submitting.</p><button onClick={() => void refresh()}>Retry balance</button></div>}
      {resources.open.error && <div className={styles.notice} role="status"><p>Orders are temporarily unavailable. Your draft is safe; please try again shortly.</p><button onClick={() => void refresh()}>Retry orders</button></div>}
      {!resources.suppliers.loaded && !resources.suppliers.error && <p role="status">Loading suppliers…</p>}
      {resources.suppliers.loaded && !resources.suppliers.error && suppliers.length === 0 && <p role="status">No active suppliers are available right now.</p>}
      <form onSubmit={(event) => void submit(event)}>
        <div className={styles.formGrid}>
          <label>Supplier<select required disabled={resources.suppliers.error || !resources.suppliers.loaded} value={supplierId} onChange={(event) => setSupplierId(event.target.value)}><option value="">Choose an active supplier</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name} · {supplier.building}, floor {supplier.floor}</option>)}</select></label>
          <label>Delivery location<input required maxLength={500} value={delivery} onChange={(event) => setDelivery(event.target.value)} placeholder="Building, floor and meeting point" /></label>
        </div>
        <fieldset><legend>Items for pickup</legend>{items.map((item, index) => <div className={styles.itemRow} key={index}>
          <label>Item {index + 1}<input required maxLength={200} value={item.name} onChange={(event) => setItems(items.map((entry, i) => i === index ? { ...entry, name: event.target.value } : entry))} placeholder="e.g. Iced coffee" /></label>
          <label>Quantity<input required type="number" min="1" step="1" value={item.quantity || ''} onChange={(event) => setItems(items.map((entry, i) => i === index ? { ...entry, quantity: Number(event.target.value) } : entry))} /></label>
          <button type="button" disabled={items.length === 1} aria-label={`Remove item ${index + 1}`} onClick={() => setItems(items.filter((_, i) => i !== index))}>Remove</button>
        </div>)}<button type="button" onClick={() => setItems([...items, { name: '', quantity: 1 }])}>+ Add item</button></fieldset>
        <div className={styles.formGrid}>
          <label>Pickup notes (optional)<textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Special instructions, substitutions, or how to collect" /></label>
          <label>Credits to award<input required type="number" min="1" step="1" max={creationAttempt || resources.credits.error ? undefined : balance?.available_credits ?? 0} value={credits} onChange={(event) => setCredits(event.target.value)} /><small>At least 1 whole credit. Available: {resources.credits.error ? 'unavailable' : balance?.available_credits ?? 'loading…'}.</small></label>
        </div>
        <button className={styles.primary} disabled={busy !== null || (!creationAttempt && (!balance || balance.available_credits < 1 || suppliers.length === 0)) || creationUnavailable} type="submit">{busy === 'create' ? 'Submitting…' : 'Submit request'}</button>
      </form>
    </section></Modal>}
    {reportOrder && <Modal id="report-problem" labelledBy="report-title" onClose={() => setReportOrder(null)} busy={busy !== null}><section className={styles.formPanel}>
      <h2 id="report-title">Report a problem</h2>
      <p>{reportOrder.supplier_snapshot?.name ?? 'Order'} · {reportOrder.items.map((item) => `${item.quantity} × ${item.name}`).join(', ')}</p>
      <p>Disputing permanently freezes order progress. It does not automatically refund or pay credits. Your reason will be visible to both participants and cannot be edited or added to by reporting again.</p>
      <form onSubmit={(event) => void dispute(event)}>
        <label htmlFor="dispute-reason">What went wrong?</label>
        <textarea id="dispute-reason" required rows={5} maxLength={2000} value={reason} disabled={busy !== null} aria-describedby="reason-help" aria-invalid={!!reportError} onChange={(event) => setReason(event.target.value)} />
        <small id="reason-help">{reason.length} / 2,000 characters</small>
        {reportError && <p role="alert" className={styles.error}>{reportError}</p>}
        <div className={styles.cardActions}><button type="button" disabled={busy !== null} onClick={() => setReportOrder(null)}>Go back</button><button className={styles.primary} type="submit" disabled={busy !== null || !reason.trim() || !!loadError}>{busy ? 'Reporting…' : 'Freeze order and report'}</button></div>
      </form>
    </section></Modal>}
    {cancelOrder && <Modal id="cancel-request" labelledBy="cancel-title" onClose={() => setCancelOrder(null)} busy={busy !== null}><section className={styles.formPanel}>
      <h2 id="cancel-title">Cancel this request?</h2><p>Reserved credits will be returned. This cannot be undone.</p>
      <div className={styles.cardActions}><button disabled={busy !== null} onClick={() => setCancelOrder(null)}>Keep request</button><button disabled={busy !== null || !!loadError} onClick={() => void update(cancelOrder, 'cancel')}>{busy ? 'Cancelling…' : 'Cancel request'}</button></div>
    </section></Modal>}
    <nav className={styles.views} aria-label="Order lists">{([['open', 'Open requests'], ['requested', 'My requests'], ['assigned', 'My deliveries']] as const).map(([key, label]) => <button key={key} aria-pressed={view === key} onClick={() => setView(key)}>{label}{key !== 'open' && orders[key].some((order) => order.status === 'disputed') ? ` · ${orders[key].filter((order) => order.status === 'disputed').length} disputed` : ''}</button>)}</nav>
    {view === 'open' && <section className={styles.filters} aria-label="Filter open requests">
      <label>Pickup location<input value={location} onChange={(event) => setLocation(event.target.value)} placeholder="Supplier or building" /></label>
      <label>Minimum credits<input type="number" min="1" step="1" value={minCredits} onChange={(event) => setMinCredits(event.target.value)} placeholder="Any" /></label>
      <label>Maximum credits<input type="number" min="1" step="1" value={maxCredits} onChange={(event) => setMaxCredits(event.target.value)} placeholder="Any" /></label>
    </section>}
    {view !== 'open' && <section className={styles.filters} aria-label="Filter and sort your orders">
      <label>Status<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as OrderFilter)}><option value="all">All orders</option><option value="disputed">Disputed</option><option value="active">Active</option><option value="finished">Finished</option></select></label>
      <label>Sort by<select value={sort} onChange={(event) => setSort(event.target.value as OrderSort)}><option value="attention">Needs attention first</option><option value="newest">Newest created</option><option value="oldest">Oldest created</option></select></label>
    </section>}
    <div className={styles.listHeading}><h2>{view === 'open' ? 'Find a favour along your way' : view === 'requested' ? 'Your requests' : 'Your deliveries'}</h2><span>Updates every 5 seconds</span></div>
    {loadError && <div role="status" className={styles.notice}><strong>{view === 'open' ? 'Open requests' : view === 'requested' ? 'Your requests' : 'Your deliveries'} are temporarily unavailable</strong><p>{resources[view].loaded ? 'Showing the last loaded orders. They may be out of date; actions will return when we reconnect.' : 'We couldn’t load this list. Please try again shortly.'} Other sections are still available.</p><button onClick={() => void refresh()}>Try again</button></div>}
    {loadingOrders ? <p role="status">Loading orders…</p> : loadError && visibleOrders.length === 0 ? null : visibleOrders.length === 0 ? <div className={styles.empty}><h3>{view === 'open' ? 'No open requests right now' : 'No matching orders'}</h3><p>{view === 'open' ? 'Try adjusting your filters or check back soon.' : 'Try another status filter, or request or accept an errand.'}</p></div> : <div className={styles.grid}>{visibleOrders.map((order) => {
      const seconds = remainingSeconds(order, now)
      const unaccepted = isUnaccepted(order)
      const expired = unaccepted && seconds === 0
      const own = order.requester_id === session.user_id
      const assigned = order.courier_id === session.user_id
      const dueAt = ['accepted', 'picked_up', 'delivered'].includes(order.status) ? order.progress_due_at : order.status === 'received' && order.credit_status === 'pending' ? order.settlement_due_at : null
      const dueLabel = order.status === 'accepted' ? 'Pickup' : order.status === 'picked_up' ? 'Delivery' : order.status === 'delivered' ? 'Receipt confirmation' : 'Credit settlement'
      return <article className={`${styles.card} ${order.status === 'disputed' ? styles.disputed : ''}`} key={order.id}>
        <div className={styles.cardTop}><span className={styles.status}>{expired ? 'Expired' : statusLabels[order.status]}</span><strong>{order.credits} <small>credits</small></strong></div>
        <h3>{order.supplier_snapshot?.name ?? 'Supplier'}</h3>
        <p className={styles.pickup}>{order.supplier_snapshot ? `${order.supplier_snapshot.building} · Floor ${order.supplier_snapshot.floor}` : 'Pickup location unavailable'}</p>
        <ul>{order.items.map((item, index) => <li key={index}>{item.quantity} × {item.name}</li>)}</ul>
        {order.pickup_notes && <p className={styles.notes}>{order.pickup_notes}</p>}
        {unaccepted && !expired && <p className={styles.countdown} aria-label="Time remaining before expiry">{Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, '0')} remaining{order.status === 'init' ? ' · Reserving credits…' : ''}</p>}
        {dueAt && <p className={styles.countdown}>{dueLabel} due <time dateTime={dueAt}>{new Date(dueAt).toLocaleString()}</time>{Date.parse(dueAt) <= now ? ' · Overdue; awaiting status update' : ''}</p>}
        {order.status === 'disputed' && <section className={styles.disputeReason} aria-label="Dispute details"><strong>Dispute reason</strong><p>{order.status_reason || 'No reason available.'}</p><p>Order progress is frozen. Reporting does not automatically refund or pay credits. Financial processing may still update.</p></section>}
        {order.status_reason && order.status !== 'disputed' && <p className={styles.notes}>{order.status_reason}</p>}
        {order.status === 'rejected' && <p>Credits could not be reserved. Check your balance before creating another request.</p>}
        <div className={styles.cardActions}>
          {order.status === 'open' && !expired && !own && <button className={styles.primary} disabled={busy !== null || !!loadError} onClick={() => void update(order, 'accept')}>{busy === order.id ? 'Updating…' : 'Accept request'}</button>}
          {order.status === 'open' && !expired && own && <button disabled={busy !== null || !!loadError} onClick={() => setCancelOrder(order)}>Cancel request</button>}
          {own && view === 'open' && <small>Your request · You cannot accept it</small>}
          {assigned && order.status === 'accepted' && <button className={styles.primary} disabled={busy !== null || !!loadError} onClick={() => void update(order, 'pickup')}>Mark picked up</button>}
          {assigned && order.status === 'picked_up' && <button className={styles.primary} disabled={busy !== null || !!loadError} onClick={() => void update(order, 'deliver')}>Mark delivered</button>}
          {own && order.status === 'delivered' && <button className={styles.primary} disabled={busy !== null || !!loadError} onClick={() => void update(order, 'receive')}>Confirm received</button>}
          {own && ['accepted', 'picked_up', 'delivered'].includes(order.status) && <small>Assigned to a courier · Cannot be cancelled</small>}
          {(own || assigned) && canDispute(order) && <button disabled={busy !== null || !!loadError} aria-haspopup="dialog" onClick={() => { setReason(''); setReportError(''); setReportOrder(order) }}>Report a problem</button>}
          {order.status === 'received' && <small>Receipt confirmed · {order.credit_status === 'rejected' ? 'Credit transfer rejected; you may report a problem' : 'Credit transfer processing'}</small>}
          {order.status === 'completed' && <small>Complete · Credits transferred</small>}
        </div>
      </article>
    })}</div>}
  </main>
}

export default Orders
