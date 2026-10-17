export default function ({ route, app }) {
  if (process.client && window.__legacyShopLoaded) {
    console.log('[tracking]', route.fullPath)
  }
}
