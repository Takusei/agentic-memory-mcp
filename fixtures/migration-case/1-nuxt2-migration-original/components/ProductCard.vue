<template>
  <article class="card">
    <h2>{{ product.name | titleCase }}</h2>
    <p>{{ product.description }}</p>
    <strong>{{ product.price | currency }}</strong>
    <button @click="$emit('add-to-cart', product)">Add to cart</button>
  </article>
</template>

<script>
export default {
  name: 'ProductCard',
  props: {
    product: {
      type: Object,
      required: true
    }
  }
}
</script>
