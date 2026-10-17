export default function ({ route }) {
  if (process.client) {
    console.log('[tracking]', route.fullPath)
  }
}
