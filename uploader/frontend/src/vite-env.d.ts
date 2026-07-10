/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'sandbox' | 'production' — set in .env.<mode>. */
  readonly VITE_APP_ENV: string
  /**
   * Base URL of the uploader backend API. Used ONLY for the optional
   * read-only GET /programs metadata fetch (account chips); export is
   * still a mock and no other endpoint is called.
   */
  readonly VITE_API_BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
