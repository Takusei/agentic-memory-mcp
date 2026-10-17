<template>
  <main class="container">
    <h2>Products</h2>
    <ProductCard
      v-for="product in products"
      :key="product.id"
      :product="product"
      @add-to-cart="addToCart"
    />
  </main>
</template>

<script>
import ProductCard from '~/components/ProductCard.vue'

export default {
  components: { ProductCard },
  async asyncData({ app, error }) {
    try {
      const products = await app.$api.getProducts()
      return { products }
    } catch (e) {
      error({ statusCode: 500, message: 'Failed to load products' })
    }
  },
  methods: {
    addToCart(product) {
      this.$store.dispatch('addToCart', product)
    }
  }
}
</script>
