export default function ({ route, store, redirect }) {
  if (route.path.startsWith('/account') && !store.state.auth.user) {
    return redirect('/login')
  }
}
