import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { CampusErrandsAPIError } from '../../api/models'
import { useCampusErrandsAPI } from '../../api/useCampusErrandsAPI'
import { useToast } from '../../components/toast/useToast'
import { useUser } from '../../components/user/UserContext'
import { routes } from '../../routes'
import type { ManagedUser, ManagedUserRole } from './models'
import styles from './AdminManagerPortal.module.css'

const PAGE_SIZE = 25

const roleContent = {
  admin: {
    tab: 'Admin',
    eyebrow: 'Administrator access',
    description: 'Review members who can create, edit, and deactivate campus suppliers.',
    placeholder: 'Search admins by username or email',
    action: 'Revoke admin access',
    empty: 'No admins found on this page.',
  },
  user: {
    tab: 'User',
    eyebrow: 'Member access',
    description: 'Find a campus member and grant supplier administration access.',
    placeholder: 'Search users by username or email',
    action: 'Grant admin access',
    empty: 'No users found on this page.',
  },
} as const

const AdminManagerPortal = () => {
  const api = useCampusErrandsAPI()
  const { showErrorToast, showSuccessToast } = useToast()
  const { session } = useUser()
  const [activeRole, setActiveRole] = useState<ManagedUserRole>('admin')
  const [query, setQuery] = useState('')
  const [appliedQuery, setAppliedQuery] = useState('')
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const requestIdRef = useRef(0)

  const loadUsers = useCallback(async (role: ManagedUserRole, search = '', pageOffset = 0) => {
    const requestId = ++requestIdRef.current
    const normalizedQuery = search.trim()
    setIsLoading(true)
    setError(null)
    setAppliedQuery(normalizedQuery)
    setOffset(pageOffset)

    try {
      const result = await api.user.authentication.listManagedUsers({
        role,
        query: normalizedQuery || undefined,
        offset: pageOffset,
        limit: PAGE_SIZE,
      })
      if (requestId === requestIdRef.current) {
        setUsers(result.items)
        setHasMore(result.has_more)
      }
    } catch (requestError) {
      if (requestId !== requestIdRef.current) return
      setError(requestError instanceof CampusErrandsAPIError
        ? requestError.message
        : 'Unable to load accounts. Please try again.')
    } finally {
      if (requestId === requestIdRef.current) setIsLoading(false)
    }
  }, [api.user.authentication])

  useEffect(() => {
    if (session.role !== 'admin_manager') return
    const initialLoad = window.setTimeout(() => void loadUsers(activeRole), 0)
    return () => {
      window.clearTimeout(initialLoad)
      requestIdRef.current += 1
    }
  }, [activeRole, loadUsers, session.role])

  if (session.role !== 'admin_manager') {
    return <Navigate to={routes.home} replace />
  }

  const content = roleContent[activeRole]

  const selectRole = (role: ManagedUserRole) => {
    if (role === activeRole) return
    requestIdRef.current += 1
    setIsLoading(true)
    setOffset(0)
    setHasMore(false)
    setQuery('')
    setAppliedQuery('')
    setUsers([])
    setActiveRole(role)
  }

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void loadUsers(activeRole, query)
  }

  const handleRoleChange = async (user: ManagedUser) => {
    const nextRole: ManagedUserRole = activeRole === 'admin' ? 'user' : 'admin'
    setUpdatingId(user.user_id)
    try {
      await api.user.authentication.updateManagedUserRole({ userId: user.user_id, role: nextRole })
      await loadUsers(activeRole, appliedQuery)
      showSuccessToast(activeRole === 'admin' ? 'Admin access revoked.' : 'Admin access granted.')
    } catch (requestError) {
      showErrorToast(requestError instanceof CampusErrandsAPIError
        ? requestError.message
        : 'Unable to update admin access. Please try again.')
    } finally {
      setUpdatingId(null)
    }
  }

  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <header className={styles.heading}>
          <p className={styles.eyebrow}>Admin manager portal</p>
          <h1>Administrator access</h1>
          <p>Manage who can maintain supplier information while keeping requester and courier access unchanged.</p>
        </header>

        <div className={styles.tabs} role="tablist" aria-label="Account roles">
          {(['admin', 'user'] as const).map((role) => (
            <button
              key={role}
              id={`${role}-tab`}
              type="button"
              role="tab"
              aria-selected={activeRole === role}
              aria-controls="managed-users-panel"
              onClick={() => selectRole(role)}
              disabled={updatingId !== null}
            >
              {roleContent[role].tab}
            </button>
          ))}
        </div>

        <section
          id="managed-users-panel"
          className={styles.panel}
          role="tabpanel"
          aria-labelledby={`${activeRole}-tab`}
        >
          <div className={styles.panelHeading}>
            <div>
              <p className={styles.eyebrow}>{content.eyebrow}</p>
              <h2>{content.tab} accounts</h2>
              <p>{content.description}</p>
            </div>
            <span aria-live="polite">{isLoading ? 'Loading…' : `${users.length} ${users.length === 1 ? 'account' : 'accounts'}`}</span>
          </div>

          <form className={styles.search} role="search" onSubmit={handleSearch}>
            <label htmlFor="managed-user-search">Filter {content.tab.toLowerCase()} accounts on each page</label>
            <div>
              <input
                id="managed-user-search"
                type="search"
                value={query}
                maxLength={254}
                placeholder={content.placeholder}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button type="submit" disabled={isLoading || updatingId !== null}>Filter</button>
            </div>
          </form>

          {error ? (
            <div className={styles.error} role="alert">
              <span>{error}</span>
              <button type="button" onClick={() => void loadUsers(activeRole, appliedQuery, offset)}>Try again</button>
            </div>
          ) : isLoading ? (
            <p className={styles.state} role="status">Loading {content.tab.toLowerCase()} accounts…</p>
          ) : users.length === 0 ? (
            <p className={styles.state}>
              {appliedQuery ? `No ${content.tab.toLowerCase()} accounts on this page match “${appliedQuery}”.` : content.empty}
            </p>
          ) : (
            <div className={styles.userList}>
              {users.map((user) => (
                <article className={styles.userRow} key={user.user_id}>
                  <div>
                    <h3>{user.username}</h3>
                    <p>{user.email}</p>
                  </div>
                  <span>{activeRole === 'admin' ? 'Administrator' : 'User'}</span>
                  <button
                    type="button"
                    onClick={() => void handleRoleChange(user)}
                    disabled={isLoading || updatingId !== null}
                  >
                    {updatingId === user.user_id ? 'Updating…' : content.action}
                  </button>
                </article>
              ))}
            </div>
          )}
          <nav aria-label="Account pages">
            <button type="button"
              disabled={isLoading || updatingId !== null || offset === 0}
              onClick={() => void loadUsers(activeRole, appliedQuery, Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </button>
            <span aria-live="polite"> Page {Math.floor(offset / PAGE_SIZE) + 1} </span>
            <button type="button"
              disabled={isLoading || updatingId !== null || !hasMore || error !== null}
              onClick={() => void loadUsers(activeRole, appliedQuery, offset + PAGE_SIZE)}>
              Next
            </button>
          </nav>
        </section>
      </main>
      <footer className={styles.footer}>Administrator access changes can take up to five minutes to take effect.</footer>
    </div>
  )
}

export default AdminManagerPortal
