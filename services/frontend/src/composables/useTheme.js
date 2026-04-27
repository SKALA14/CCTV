import { ref, watch } from 'vue'

const STORAGE_KEY = 'cctv_theme'
const isDark = ref(localStorage.getItem(STORAGE_KEY) !== 'light')

function apply(dark) {
  document.documentElement.classList.toggle('light', !dark)
  document.documentElement.classList.toggle('dark', dark)
}

apply(isDark.value)

watch(isDark, (val) => {
  apply(val)
  localStorage.setItem(STORAGE_KEY, val ? 'dark' : 'light')
})

export function useTheme() {
  function toggle() { isDark.value = !isDark.value }
  return { isDark, toggle }
}
