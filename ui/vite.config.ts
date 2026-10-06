import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode, command }) => {
  const env = loadEnv(mode, process.cwd(), '')
  if (command === 'serve' && !env.INTERNAL_GATEWAY_URL?.trim()) {
    throw new Error('INTERNAL_GATEWAY_URL must be set for the development proxy')
  }
  const gatewayProxy = {
    target: env.INTERNAL_GATEWAY_URL,
    changeOrigin: true,
    cookieDomainRewrite: '',
  }

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/supplier-api': { ...gatewayProxy },
        '/user-api': { ...gatewayProxy },
      },
    },
    define: {
      'import.meta.env.VITE_USER_API_URL': JSON.stringify(env.VITE_USER_API_URL || '/user-api'),
      'import.meta.env.VITE_SUPPLIER_API_URL': JSON.stringify(env.VITE_SUPPLIER_API_URL || '/supplier-api'),
    },
  }
})
