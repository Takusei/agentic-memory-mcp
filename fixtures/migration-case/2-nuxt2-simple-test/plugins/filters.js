import Vue from 'vue'

Vue.filter('yen', value => {
  if (value === null || value === undefined) return '¥0'
  return `¥${Number(value).toLocaleString('ja-JP')}`
})
