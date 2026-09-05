import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

const releaseManifest = JSON.parse(
  readFileSync(new URL('../release-manifest.json', import.meta.url), 'utf8'),
) as {
  schemaVersion: number
  productVersion: string
  frontendVersion: string
  apiVersion: string
  releaseDate: string
}

export default defineConfig({
  define: {
    'process.env.NEXT_PUBLIC_RELEASE_SCHEMA_VERSION': JSON.stringify(String(releaseManifest.schemaVersion)),
    'process.env.NEXT_PUBLIC_PRODUCT_VERSION': JSON.stringify(releaseManifest.productVersion),
    'process.env.NEXT_PUBLIC_FRONTEND_VERSION': JSON.stringify(releaseManifest.frontendVersion),
    'process.env.NEXT_PUBLIC_API_VERSION': JSON.stringify(releaseManifest.apiVersion),
    'process.env.NEXT_PUBLIC_RELEASE_DATE': JSON.stringify(releaseManifest.releaseDate),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
