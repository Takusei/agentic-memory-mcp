<template>
  <main>
    <nuxt-link to="/">Back</nuxt-link>
    <section v-if="item" class="card">
      <h1>{{ item.name }}</h1>
      <p>{{ item.description }}</p>
      <strong>{{ item.price | yen }}</strong>
    </section>
    <p v-else class="error">Item not found</p>
  </main>
</template>

<script>
export default {
  async asyncData({ params, $api, error }) {
    const item = await $api.getItem(params.id)
    if (!item) {
      error({ statusCode: 404, message: 'Item not found' })
      return { item: null }
    }
    return { item }
  }
}
</script>
