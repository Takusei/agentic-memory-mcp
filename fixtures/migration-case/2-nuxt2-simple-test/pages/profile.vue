<template>
  <main>
    <h1>Profile</h1>
    <p>Name: {{ user.name }}</p>
  </main>
</template>

<script>
export default {
  middleware: 'auth',
  computed: {
    user() {
      return this.$store.state.auth.user
    }
  }
}
</script>
