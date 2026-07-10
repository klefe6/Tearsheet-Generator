import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Frontend-only dev config. Vite serves on 5173 by default — well clear of the
// protected tearsheet ports (8301/8302/8303/8304 and the 83xx preview block).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: false,
    open: false,
  },
})
