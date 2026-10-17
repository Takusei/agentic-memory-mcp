export default {
  ssr: true,
  target: 'server',
  head: {
    title: 'Nuxt2 Simple Migration Case',
    meta: [
      { charset: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' }
    ]
  },
  css: ['~/assets/main.css'],
  plugins: [
    '~/plugins/filters.js',
    '~/plugins/api.js'
  ],
  modules: ['@nuxtjs/axios'],
  axios: {
    baseURL: process.env.API_BASE_URL || 'https://example.test/api'
  },
  publicRuntimeConfig: {
    apiBaseUrl: process.env.API_BASE_URL || 'https://example.test/api'
  },
  router: {
    middleware: ['tracking']
  }
}
