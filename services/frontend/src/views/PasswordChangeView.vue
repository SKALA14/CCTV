<template>
  <div class="flex items-center justify-center h-full">
    <div class="w-full max-w-sm p-8 rounded-2xl" style="background: var(--bg-card); border: 1px solid var(--border);">
      <h2 class="text-lg font-bold mb-1" style="color: var(--text-primary);">비밀번호 변경</h2>
      <p v-if="authStore.mustChangePwd" class="text-sm mb-5" style="color: var(--text-muted);">
        초기 비밀번호를 변경해야 합니다.
      </p>
      <p v-else class="text-sm mb-5" style="color: var(--text-muted);">새 비밀번호를 입력하세요.</p>

      <form @submit.prevent="handleSubmit" class="space-y-3">
        <input
          v-model="form.current_password"
          type="password"
          placeholder="현재 비밀번호"
          class="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        />
        <input
          v-model="form.new_password"
          type="password"
          placeholder="새 비밀번호 (8자 이상, 영문+숫자 포함)"
          class="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        />
        <div v-if="error" class="text-red-400 text-xs px-1">{{ error }}</div>
        <button
          type="submit"
          :disabled="loading || !form.current_password || !form.new_password"
          class="w-full py-2.5 rounded-xl text-sm font-semibold transition-opacity"
          :class="loading ? 'opacity-50 cursor-not-allowed' : ''"
          style="background: #2563eb; color: white;"
        >
          {{ loading ? '변경 중...' : '비밀번호 변경' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import { changeMyPassword } from '../api/users.js'

const router    = useRouter()
const authStore = useAuthStore()

const form    = ref({ current_password: '', new_password: '' })
const loading = ref(false)
const error   = ref(null)

async function handleSubmit() {
  loading.value = true
  error.value   = null
  try {
    await changeMyPassword(form.value)
    // must_change_password 플래그 갱신
    await authStore.fetchMe()
    router.replace({ name: 'dashboard' })
  } catch (e) {
    error.value = e.response?.data?.detail ?? e.message
  } finally {
    loading.value = false
  }
}
</script>
