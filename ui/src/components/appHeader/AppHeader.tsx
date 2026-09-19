import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useCampusErrandsAPI } from '../../api/useCampusErrandsAPI'
import { routes } from '../../routes'
import { useToast } from '../toast/useToast'
import { useUser } from '../user/UserContext'
import styles from './AppHeader.module.css'

const AppHeader = () => {
  const api = useCampusErrandsAPI()
  const location = useLocation()
  const navigate = useNavigate()
  const { showErrorToast } = useToast()
  const { activeRole, profile, setActiveRole } = useUser()
  const [isOpen, setIsOpen] = useState(false)
  const [isSigningOut, setIsSigningOut] = useState(false)
  const dialogRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog || !isOpen) return

    const previousOverflow = document.body.style.overflow
    dialog.showModal()
    document.body.style.overflow = 'hidden'

    return () => {
      if (dialog.open) dialog.close()
      document.body.style.overflow = previousOverflow
    }
  }, [isOpen])

  const handleSignOut = async () => {
    setIsSigningOut(true)
    try {
      await api.user.authentication.signOut()
      navigate(routes.signIn, { replace: true })
    } catch {
      showErrorToast('Unable to sign out. Please try again.')
      setIsSigningOut(false)
    }
  }

  const initials = profile.username.trim().slice(0, 2).toUpperCase() || 'U'

  return (
    <header className={styles.header}>
      <Link className={styles.wordmark} to={routes.home}>campus<em>errands.</em></Link>
      <nav className={styles.navigation} aria-label="Main navigation">
        <Link to={routes.home} aria-current={location.pathname === routes.home ? 'page' : undefined}>Home</Link>
        <Link to={routes.suppliers} aria-current={location.pathname === routes.suppliers ? 'page' : undefined}>Suppliers</Link>
        <button
          className={styles.accountButton}
          type="button"
          aria-label="Open account and role settings"
          aria-expanded={isOpen}
          aria-controls="account-drawer"
          onClick={() => setIsOpen(true)}
        >
          {initials}
        </button>
      </nav>

      <dialog
        id="account-drawer"
        ref={dialogRef}
        className={styles.drawer}
        aria-labelledby="account-drawer-title"
        onCancel={(event) => {
          event.preventDefault()
          setIsOpen(false)
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) setIsOpen(false)
        }}
      >
        <div className={styles.drawerContent}>
          <div className={styles.drawerHeading}>
            <div>
              <p className={styles.eyebrow}>Account</p>
              <h2 id="account-drawer-title">Your account</h2>
            </div>
            <button className={styles.closeButton} type="button" onClick={() => setIsOpen(false)} aria-label="Close account settings">Close</button>
          </div>

          <div className={styles.identity}>
            <span>{initials}</span>
            <div>
              <strong>{profile.username}</strong>
              <p>{profile.email}</p>
            </div>
          </div>

          <fieldset className={styles.roleControl}>
            <legend>Use Campus Errands as</legend>
            <div>
              <button type="button" aria-pressed={activeRole === 'requester'} onClick={() => setActiveRole('requester')}>Requester</button>
              <button type="button" aria-pressed={activeRole === 'courier'} onClick={() => setActiveRole('courier')}>Courier</button>
            </div>
            <p>{activeRole === 'requester' ? 'Ask someone nearby for a pickup.' : 'Help someone with a campus delivery.'}</p>
          </fieldset>

          <nav className={styles.accountLinks} aria-label="Account navigation">
            <Link to={routes.profile} onClick={() => setIsOpen(false)}>
              <span>Profile</span>
              <span aria-hidden="true">→</span>
            </Link>
          </nav>

          <button className={styles.signOutButton} type="button" onClick={() => void handleSignOut()} disabled={isSigningOut}>
            {isSigningOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </dialog>
    </header>
  )
}

export default AppHeader
