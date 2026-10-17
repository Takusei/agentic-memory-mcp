import Vue from 'vue'

Vue.filter('currency', value => {
  if (typeof value !== 'number') return value
  return `$${value.toFixed(2)}`
})

Vue.filter('titleCase', value => {
  if (!value) return ''
  return value.replace(/\w\S*/g, text => text.charAt(0).toUpperCase() + text.substr(1).toLowerCase())
})
