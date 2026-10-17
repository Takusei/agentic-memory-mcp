export const state = () => ({
  user: null
})

export const mutations = {
  SET_USER(state, user) {
    state.user = user
  }
}

export const actions = {
  async nuxtServerInit({ commit }, { req, app }) {
    const token = req.headers.cookie && req.headers.cookie.includes('demo_auth=true')
    if (token) {
      const user = await app.$api.getProfile()
      commit('SET_USER', user)
    }
  },

  async loadProfile({ commit }, { app }) {
    const user = await app.$api.getProfile()
    commit('SET_USER', user)
  }
}
