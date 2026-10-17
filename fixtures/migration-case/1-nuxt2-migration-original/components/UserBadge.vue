<template>
  <div v-if="user" class="card">
    Logged in as {{ user.name }} / {{ user.email }}
  </div>
</template>

<script>
export default {
  name: 'UserBadge',
  computed: {
    user() {
      return this.$store.state.auth.user
    }
  }
}
</script>
