/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'sandbox' | 'production' — set in .env.<mode>. */
  readonly VITE_APP_ENV: string
  /** Base URL of the uploader backend API. Reserved for future export wiring. */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
