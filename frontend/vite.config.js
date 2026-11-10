import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/orgs': 'http://127.0.0.1:8000',
      '/teams': 'http://127.0.0.1:8000',
      '/documents': 'http://127.0.0.1:8000',
      '/query': 'http://127.0.0.1:8000',
      '/feedback': 'http://127.0.0.1:8000',
      '/evals': 'http://127.0.0.1:8000',
      '/api_keys': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
