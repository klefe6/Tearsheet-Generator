import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Frontend-only dev config. Standard local port 5173 — well clear of the
// protected tearsheet ports (8301/8302/8303/8304 and the 83xx preview block).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    host: '127.0.0.1',
    open: false,
  },
})
