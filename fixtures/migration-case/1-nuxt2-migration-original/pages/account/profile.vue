<template>
  <main class="container">
    <h2>Profile</h2>
    <UserBadge />
  </main>
</template>

<script>
export default {
  middleware: 'auth',
  async fetch({ store, app }) {
    await store.dispatch('auth/loadProfile', { app })
  }
}
</script>
