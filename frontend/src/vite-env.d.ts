/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** base URL of the API; defaults to /api (the Vite dev proxy) */
  readonly VITE_API_BASE?: string;
}
