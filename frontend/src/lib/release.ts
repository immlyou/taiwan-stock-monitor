export interface ReleaseManifest {
  schemaVersion: number
  productVersion: string
  frontendVersion: string
  apiVersion: string
  releaseDate: string
}

function requiredBuildValue(name: string, value: string | undefined): string {
  if (!value) throw new Error(`Missing release manifest value: ${name}`)
  return value
}

/** Values are injected from the repository-root release-manifest.json at build time. */
export const RELEASE_MANIFEST: Readonly<ReleaseManifest> = Object.freeze({
  schemaVersion: Number(
    requiredBuildValue('schemaVersion', process.env.NEXT_PUBLIC_RELEASE_SCHEMA_VERSION),
  ),
  productVersion: requiredBuildValue(
    'productVersion',
    process.env.NEXT_PUBLIC_PRODUCT_VERSION,
  ),
  frontendVersion: requiredBuildValue(
    'frontendVersion',
    process.env.NEXT_PUBLIC_FRONTEND_VERSION,
  ),
  apiVersion: requiredBuildValue('apiVersion', process.env.NEXT_PUBLIC_API_VERSION),
  releaseDate: requiredBuildValue('releaseDate', process.env.NEXT_PUBLIC_RELEASE_DATE),
})

export const CURRENT_VERSION = `v${RELEASE_MANIFEST.productVersion}` as `v${number}.${number}.${number}`
export const FRONTEND_VERSION = RELEASE_MANIFEST.frontendVersion
export const API_VERSION = RELEASE_MANIFEST.apiVersion
