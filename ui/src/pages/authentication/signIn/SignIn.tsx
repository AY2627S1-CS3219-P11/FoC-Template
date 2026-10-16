import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import AuthLayout from '../../../components/authLayout/AuthLayout'
import { useToast } from '../../../components/toast/useToast'
import { routes } from '../../../routes'
import { login } from '../../../auth/keycloak'
import styles from '../Authentication.module.css'

const SignIn = () => {
  const [isPending, setIsPending] = useState(false)
  const location = useLocation()
  const { showErrorToast } = useToast()
  const returnTo = (location.state as { returnTo?: string } | null)?.returnTo

  return <AuthLayout eyebrow="NUS student community" title="Sign In">
    <button className={styles.submit} disabled={isPending} onClick={async () => {
      setIsPending(true)
      try { await login(returnTo ?? routes.home) }
      catch { showErrorToast('Unable to sign in. Please try again.'); setIsPending(false) }
    }}>{isPending ? 'Opening sign-in…' : 'Sign in'}</button>
    <p className={styles.footer}>New here? <Link to={routes.signUp}>Create an account</Link></p>
  </AuthLayout>
}

export default SignIn
