<!-- 로그인 화면 -->
<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-900">
    <div class="w-full max-w-sm bg-gray-800 rounded-xl p-8 shadow-lg">
      <h1 class="text-2xl font-bold text-white mb-6 text-center">CCTV 관제 시스템</h1>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">아이디</label>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            class="w-full bg-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="아이디를 입력하세요"
          />
        </div>

        <div>
          <label class="block text-sm text-gray-400 mb-1">비밀번호</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="w-full bg-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="비밀번호를 입력하세요"
          />
        </div>

        <p v-if="errorMsg" class="text-red-400 text-sm text-center">{{ errorMsg }}</p>

        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 text-white font-semibold rounded-lg py-2 transition-colors"
        >
          {{ loading ? '로그인 중...' : '로그인' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'

const router  = useRouter()
const auth    = useAuthStore()

const username = ref('')
const password = ref('')
const loading  = ref(false)
const errorMsg = ref('')

async function handleLogin() {
    if (!username.value || !password.value) {
        errorMsg.value = '아이디와 비밀번호를 입력해주세요'
        return
    }
    loading.value  = true
    errorMsg.value = ''
    try {
        await auth.login(username.value, password.value)
        router.replace('/')
    } catch (e) {
        errorMsg.value = e.response?.data?.detail || '로그인에 실패했습니다'
    } finally {
        loading.value = false
    }
}
</script>
