import { useState } from 'react'
import { manageAccount } from '../../auth/keycloak'
import { useToast } from '../../components/toast/useToast'
import { useUser } from '../../components/user/UserContext'
import styles from './Profile.module.css'

const Profile = () => {
  const { activeRole, profile } = useUser()
  const { showErrorToast } = useToast()
  const [isPending, setIsPending] = useState(false)

  return <div className={styles.page}>
    <main className={styles.main}>
      <div className={styles.heading}>
        <p className={styles.eyebrow}>Your account</p>
        <h1>Profile</h1>
        <p>Manage your identity and password on our account service.</p>
      </div>
      <section className={styles.profileCard} aria-labelledby="profile-details-title">
        <div className={styles.cardHeading}>
          <h2 id="profile-details-title">Personal details</h2>
          <span>{activeRole === 'requester' ? 'Requester' : 'Courier'}</span>
        </div>
        <dl><dt>Username</dt><dd>{profile.username}</dd><dt>Email</dt><dd>{profile.email}</dd></dl>
        <button disabled={isPending} onClick={async () => {
          setIsPending(true)
          try { await manageAccount() }
          catch { showErrorToast('Unable to open account settings.'); setIsPending(false) }
        }}>Manage account</button>
      </section>
    </main>
    <footer className={styles.footer}>Campus Errands · Small favours, better campus days.</footer>
  </div>
}

export default Profile
