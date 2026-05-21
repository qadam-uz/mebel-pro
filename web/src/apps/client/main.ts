import '@/shared/assets/app.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import { configureApi } from '@/shared/api'
import { i18n } from '@/shared/i18n'
import App from './App.vue'
import router from './router'

configureApi({ app: 'client', loginPath: '/client.html' })

const app = createApp(App)
app.use(createPinia())
app.use(i18n)
app.use(router)
app.mount('#app')
