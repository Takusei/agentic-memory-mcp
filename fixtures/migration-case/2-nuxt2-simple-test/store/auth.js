export const state = () => ({
  loggedIn: true,
  user: {
    id: 'u-1',
    name: 'Demo User'
  }
})

export const mutations = {
  login(state, user) {
    state.loggedIn = true
    state.user = user
  },
  logout(state) {
    state.loggedIn = false
    state.user = null
  }
}
