import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/supplier-api': {
          target: env.VITE_SUPPLIER_API_PROXY_TARGET || 'http://127.0.0.1:3001',
          changeOrigin: true,
          cookieDomainRewrite: '',
          rewrite: (path) => path.replace(/^\/supplier-api(?=\/|$)/, ''),
        },
        '/user-api': {
          target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5005',
          changeOrigin: true,
          cookieDomainRewrite: '',
          rewrite: (path) => path.replace(/^\/user-api(?=\/|$)/, ''),
        },
      },
    },
    define: {
      'import.meta.env.VITE_USER_API_URL': JSON.stringify(env.VITE_USER_API_URL || '/user-api'),
      'import.meta.env.VITE_SUPPLIER_API_URL': JSON.stringify(env.VITE_SUPPLIER_API_URL || '/supplier-api'),
    },
  }
})
