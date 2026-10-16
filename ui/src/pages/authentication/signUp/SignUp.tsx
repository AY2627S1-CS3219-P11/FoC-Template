import { useState } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../../../components/authLayout/AuthLayout'
import { useToast } from '../../../components/toast/useToast'
import { register } from '../../../auth/keycloak'
import { routes } from '../../../routes'
import styles from '../Authentication.module.css'

const SignUp = () => {
  const [isPending, setIsPending] = useState(false)
  const { showErrorToast } = useToast()

  return <AuthLayout eyebrow="NUS student community" title="Create an account">
    <p>Create your account securely on our sign-in service.</p>
    <button className={styles.submit} disabled={isPending} onClick={async () => {
      setIsPending(true)
      try { await register() }
      catch { showErrorToast('Unable to open registration. Please try again.'); setIsPending(false) }
    }}>{isPending ? 'Opening registration…' : 'Create an account'}</button>
    <p className={styles.footer}>Already have an account? <Link to={routes.signIn}>Sign in</Link></p>
  </AuthLayout>
}

export default SignUp
