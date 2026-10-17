<template>
  <main class="container">
    <ProductCard :product="product" @add-to-cart="addToCart" />
  </main>
</template>

<script>
import ProductCard from '~/components/ProductCard.vue'

export default {
  components: { ProductCard },
  validate({ params }) {
    return /^\d+$/.test(params.id)
  },
  async fetch({ app, params, store }) {
    const product = await app.$api.getProduct(params.id)
    store.commit('ADD_TO_CART', product)
  },
  computed: {
    product() {
      return this.$store.state.cart[this.$store.state.cart.length - 1]
    }
  },
  methods: {
    addToCart(product) {
      this.$store.dispatch('addToCart', product)
    }
  }
}
</script>
