export default {
  ssr: true,
  target: 'server',

  head: {
    titleTemplate: '%s - Legacy Shop',
    title: 'Legacy Shop',
    meta: [
      { charset: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { hid: 'description', name: 'description', content: 'Nuxt2 migration benchmark app' }
    ]
  },

  css: ['~/assets/main.css'],

  plugins: [
    '~/plugins/filters.js',
    '~/plugins/api-client.js',
    { src: '~/plugins/browser-only.js', mode: 'client' }
  ],

  components: true,

  buildModules: [
    '@nuxtjs/eslint-module'
  ],

  modules: [
    '@nuxtjs/axios',
    '@nuxtjs/dotenv'
  ],

  axios: {
    baseURL: process.env.API_BASE_URL || 'http://localhost:3000/api'
  },

  router: {
    middleware: ['auth', 'tracking']
  },

  serverMiddleware: [
    { path: '/api', handler: '~/server-middleware/api.js' }
  ],

  env: {
    legacyFeatureFlag: process.env.LEGACY_FEATURE_FLAG || 'enabled'
  },

  build: {
    transpile: [],
    extend(config, ctx) {
      if (ctx.isClient) {
        config.devtool = 'source-map'
      }
    }
  }
}
