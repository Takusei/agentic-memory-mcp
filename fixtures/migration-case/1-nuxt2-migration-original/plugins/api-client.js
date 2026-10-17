export default function ({ $axios }, inject) {
  const api = {
    getProducts() {
      return $axios.$get('/products')
    },
    getProduct(id) {
      return $axios.$get(`/products/${id}`)
    },
    getProfile() {
      return $axios.$get('/profile')
    }
  }

  inject('api', api)
}
