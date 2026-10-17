export const state = () => ({
  cart: []
})

export const mutations = {
  ADD_TO_CART(state, product) {
    state.cart.push(product)
  }
}

export const actions = {
  addToCart({ commit }, product) {
    commit('ADD_TO_CART', product)
  }
}
