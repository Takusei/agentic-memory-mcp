<template>
  <main>
    <h1>Simple Nuxt2 Shop</h1>
    <p>Welcome, {{ userName }}</p>
    <ItemCard v-for="item in items" :key="item.id" :item="item" />
  </main>
</template>

<script>
import ItemCard from '~/components/ItemCard.vue'

export default {
  components: { ItemCard },
  async asyncData({ $api }) {
    const items = await $api.listItems()
    return { items }
  },
  computed: {
    userName() {
      return this.$store.state.auth.user ? this.$store.state.auth.user.name : 'Guest'
    }
  }
}
</script>
