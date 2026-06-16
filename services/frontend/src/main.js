// 앱 진입점 — 테마 선적용 후 Pinia·라우터 등록·마운트
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router/index.js'
import './style.css'

// 저장된 테마를 렌더링 전에 즉시 적용 (깜빡임 방지)
const savedTheme = localStorage.getItem('cctv_theme')
if (savedTheme === 'dark') {
  document.documentElement.classList.add('dark')
} else {
  document.documentElement.classList.add('light')
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')