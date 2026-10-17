<template>
  <main class="container">
    <UserBadge />
    <h2>Home</h2>
    <p>Feature flag: {{ legacyFlag }}</p>
    <p>Cart size: {{ cartSize }}</p>
  </main>
</template>

<script>
export default {
  asyncData({ env }) {
    return {
      legacyFlag: env.legacyFeatureFlag
    }
  },
  computed: {
    cartSize() {
      return this.$store.state.cart.length
    }
  }
}
</script>
