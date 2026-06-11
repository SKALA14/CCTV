<template>
  <div class="p-6 h-full overflow-auto">
    <!-- 계정 패널 — admin 자기 현장의 user 계정 관리 -->
    <div class="max-w-3xl">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-bold" style="color: var(--text-primary);">{{ siteName }} — 계정</h2>
        <button
          @click="openUserForm"
          class="text-xs px-3 py-1.5 rounded-lg font-semibold"
          style="background: #2563eb; color: white;"
        >+ 추가</button>
      </div>

      <div v-if="usersLoading" class="text-sm" style="color: var(--text-muted);">불러오는 중...</div>
      <div v-else-if="users.length === 0" class="text-sm" style="color: var(--text-muted);">등록된 계정이 없습니다.</div>

      <div
        v-else
        class="rounded-xl overflow-hidden"
        style="border: 1px solid var(--border);"
      >
        <table class="w-full text-sm">
          <thead>
            <tr style="background: var(--bg-elevated);">
              <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">username</th>
              <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">role</th>
              <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">비밀번호</th>
              <th class="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="u in users"
              :key="u.id"
              style="border-top: 1px solid var(--border);"
            >
              <td class="px-4 py-3" style="color: var(--text-primary);">
                {{ u.username }}
                <span v-if="u.must_change_password" class="ml-1 text-xs text-yellow-500">(초기)</span>
              </td>
              <td class="px-4 py-3">
                <span
                  class="px-2 py-0.5 rounded text-xs font-bold uppercase"
                  :style="u.role === 'admin'
                    ? 'background: #7f1d1d; color: #fca5a5;'
                    : 'background: #1f2937; color: #9ca3af;'"
                >{{ u.role }}</span>
              </td>
              <td class="px-4 py-3">
                <button
                  @click="handleResetPassword(u)"
                  class="text-xs hover:underline"
                  style="color: #f59e0b;"
                >초기화</button>
              </td>
              <td class="px-4 py-3 text-right">
                <button
                  v-if="u.id !== auth.user?.user_id"
                  @click="handleDeleteUser(u)"
                  class="text-xs hover:underline"
                  style="color: #ef4444;"
                >삭제</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 계정 추가 모달 -->
    <div v-if="showUserForm" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showUserForm = false">
      <div class="p-6 rounded-2xl w-80" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h3 class="font-bold mb-4" style="color: var(--text-primary);">계정 추가</h3>
        <input
          v-model="newUser.username"
          type="text"
          placeholder="username"
          class="w-full px-4 py-2.5 rounded-xl text-sm mb-3 outline-none"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        />
        <select
          v-model="newUser.role"
          class="app-select w-full px-4 py-2.5 rounded-xl text-sm mb-3"
        >
          <option value="user">user — 조회·검색 (관제)</option>
          <option value="admin">admin — 콘솔 관리</option>
        </select>
        <div v-if="userFormError" class="text-red-400 text-xs mb-3">{{ userFormError }}</div>
        <div class="flex gap-2">
          <button @click="showUserForm = false" class="flex-1 py-2 rounded-xl text-sm" style="background: var(--bg-elevated); color: var(--text-muted);">취소</button>
          <button @click="handleCreateUser" :disabled="!newUser.username.trim()" class="flex-1 py-2 rounded-xl text-sm font-semibold" style="background: #2563eb; color: white;">추가</button>
        </div>
      </div>
    </div>

    <!-- 초기 비밀번호 표시 모달 -->
    <div v-if="initialPassword" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div class="p-6 rounded-2xl w-80" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h3 class="font-bold mb-2" style="color: var(--text-primary);">초기 비밀번호</h3>
        <p class="text-xs mb-4" style="color: var(--text-muted);">이 비밀번호는 지금만 표시됩니다. 담당자에게 전달하세요.</p>
        <code class="block text-center text-lg font-mono py-4 rounded-xl" style="background: var(--bg-elevated); color: var(--text-primary);">{{ initialPassword }}</code>
        <button @click="initialPassword = null" class="mt-4 w-full py-2.5 rounded-xl text-sm font-semibold" style="background: #2563eb; color: white;">확인</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getUsers, createUser, deleteUser, resetPassword } from '../api/users.js'
import { useAuthStore } from '../stores/authStore.js'

const auth = useAuthStore()
const siteId   = computed(() => auth.user?.site_id)
const siteName = computed(() => auth.user?.site_name || '내 현장')

const users        = ref([])
const usersLoading = ref(true)

const showUserForm  = ref(false)
const newUser       = ref({ username: '', role: 'user' })
const userFormError = ref(null)

const initialPassword = ref(null)

onMounted(loadUsers)

async function loadUsers() {
  usersLoading.value = true
  try {
    users.value = await getUsers(siteId.value)
  } catch (e) {
    console.error('[AdminView] 계정 목록 로드 실패:', e)
  } finally {
    usersLoading.value = false
  }
}

function openUserForm() {
  newUser.value       = { username: '', role: 'user' }
  userFormError.value = null
  showUserForm.value  = true
}

async function handleCreateUser() {
  if (!newUser.value.username.trim()) return
  userFormError.value = null
  try {
    const res = await createUser(siteId.value, newUser.value)
    initialPassword.value = res.initial_password
    users.value.push(res.user)
    showUserForm.value = false
  } catch (e) {
    userFormError.value = e.response?.data?.detail ?? e.message
  }
}

async function handleDeleteUser(u) {
  if (!confirm(`${u.username} 계정을 삭제하시겠습니까?`)) return
  try {
    await deleteUser(siteId.value, u.id)
    users.value = users.value.filter(x => x.id !== u.id)
  } catch (e) {
    alert(e.response?.data?.detail ?? e.message)
  }
}

async function handleResetPassword(u) {
  if (!confirm(`${u.username}의 비밀번호를 초기화하시겠습니까?`)) return
  try {
    const res = await resetPassword(siteId.value, u.id)
    initialPassword.value = res.new_password
  } catch (e) {
    alert(e.response?.data?.detail ?? e.message)
  }
}
</script>
