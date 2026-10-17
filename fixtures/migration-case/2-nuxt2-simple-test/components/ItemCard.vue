<template>
  <article class="card">
    <h2>{{ item.name }}</h2>
    <p>{{ item.price | yen }}</p>
    <nuxt-link :to="`/items/${item.id}`">View detail</nuxt-link>
  </article>
</template>

<script>
export default {
  name: 'ItemCard',
  props: {
    item: {
      type: Object,
      required: true
    }
  }
}
</script>
