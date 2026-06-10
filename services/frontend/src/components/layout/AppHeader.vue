<template>
  <header class="app-header">
    <span class="logo">AI CCTV</span>

    <!-- 사용자 정보 + 로그아웃 -->
    <div v-if="auth.isLoggedIn" class="flex items-center gap-3 text-sm text-gray-300">
      <span>{{ auth.user.username }}</span>
      <span
        class="px-2 py-0.5 rounded text-xs"
        :class="auth.isAdmin ? 'bg-red-800 text-red-200' : 'bg-gray-700 text-gray-300'"
      >
        {{ auth.isAdmin ? 'admin' : 'user' }}
      </span>
      <button
        @click="handleLogout"
        class="text-gray-400 hover:text-white transition-colors"
      >
        로그아웃
      </button>
    </div>
  </header>
</template>

<script setup>
import { useAuthStore } from '../../stores/authStore.js'
import { useRouter } from 'vue-router'

const auth   = useAuthStore()
const router = useRouter()

async function handleLogout() {
  await auth.logout()
  router.replace('/login')
}
</script>
