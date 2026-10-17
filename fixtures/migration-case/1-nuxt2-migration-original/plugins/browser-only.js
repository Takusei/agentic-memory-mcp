export default function ({ app }) {
  window.__legacyShopLoaded = true
  window.addEventListener('beforeunload', () => {
    console.log('Leaving legacy shop')
  })
}
