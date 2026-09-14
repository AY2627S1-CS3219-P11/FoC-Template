import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCampusErrandsAPI } from '../../api/useCampusErrandsAPI'
import { useToast } from '../../components/toast/useToast'
import { routes } from '../../routes'
import styles from './Home.module.css'

const Home = () => {
  const [isSigningOut, setIsSigningOut] = useState(false)
  const api = useCampusErrandsAPI()
  const navigate = useNavigate()
  const { showErrorToast } = useToast()

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

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.wordmark}>campus<em>errands.</em></span>
        <button type="button" onClick={handleSignOut} disabled={isSigningOut}>
          {isSigningOut ? 'Signing out…' : 'Sign out'}
        </button>
      </header>
      <main className={styles.main}>
        <p className={styles.eyebrow}>NUS student community</p>
        <h1>What can we help<br />you carry today?</h1>
        <p className={styles.intro}>
          Ask for a small favour, help someone already on your route, and make the spaces between classes count.
        </p>
        <section className={styles.cards} aria-label="Campus Errands overview">
          <article>
            <span>01</span>
            <h2>Request an errand</h2>
            <p>Share what you need, where it is, and when it should arrive.</p>
          </article>
          <article>
            <span>02</span>
            <h2>Help nearby</h2>
            <p>Pick up an open request that already fits your route across campus.</p>
          </article>
          <article>
            <span>03</span>
            <h2>Pass it on</h2>
            <p>Earn credits for helping and use them when you need a hand later.</p>
          </article>
        </section>
      </main>
      <footer className={styles.footer}>Campus Errands · Small favours, better campus days.</footer>
    </div>
  )
}

export default Home
