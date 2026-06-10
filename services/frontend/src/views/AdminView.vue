<template>
  <div class="p-6 flex gap-6 h-full overflow-auto">
    <!-- 현장 패널 -->
    <div class="w-72 flex-shrink-0">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-bold" style="color: var(--text-primary);">현장 목록</h2>
        <button
          @click="openSiteForm"
          class="text-xs px-3 py-1.5 rounded-lg font-semibold"
          style="background: #2563eb; color: white;"
        >+ 추가</button>
      </div>

      <div v-if="sitesLoading" class="text-sm" style="color: var(--text-muted);">불러오는 중...</div>
      <div v-else-if="sites.length === 0" class="text-sm" style="color: var(--text-muted);">등록된 현장이 없습니다.</div>

      <div
        v-for="site in sites"
        :key="site.id"
        class="p-3 rounded-xl mb-2 cursor-pointer transition-colors"
        :style="selectedSite?.id === site.id
          ? 'background: rgba(37,99,235,0.2); border: 1px solid #2563eb;'
          : 'background: var(--bg-card); border: 1px solid var(--border);'"
        @click="selectSite(site)"
      >
        <div class="font-medium text-sm" style="color: var(--text-primary);">{{ site.name }}</div>
        <div class="text-xs mt-0.5" style="color: var(--text-muted);">계정 {{ site.user_count }}명</div>
      </div>
    </div>

    <!-- 계정 패널 -->
    <div class="flex-1" v-if="selectedSite">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-bold" style="color: var(--text-primary);">{{ selectedSite.name }} — 계정</h2>
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

    <div v-else-if="!sitesLoading" class="flex-1 flex items-center justify-center">
      <p class="text-sm" style="color: var(--text-muted);">현장을 선택하면 계정 목록이 표시됩니다.</p>
    </div>

    <!-- 현장 추가 모달 -->
    <div v-if="showSiteForm" class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" @click.self="showSiteForm = false">
      <div class="p-6 rounded-2xl w-80" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h3 class="font-bold mb-4" style="color: var(--text-primary);">현장 추가</h3>
        <input
          v-model="newSiteName"
          type="text"
          placeholder="현장 이름"
          class="w-full px-4 py-2.5 rounded-xl text-sm mb-3 outline-none"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
          @keyup.enter="handleCreateSite"
        />
        <div v-if="siteFormError" class="text-red-400 text-xs mb-3">{{ siteFormError }}</div>
        <div class="flex gap-2">
          <button @click="showSiteForm = false" class="flex-1 py-2 rounded-xl text-sm" style="background: var(--bg-elevated); color: var(--text-muted);">취소</button>
          <button @click="handleCreateSite" :disabled="!newSiteName.trim()" class="flex-1 py-2 rounded-xl text-sm font-semibold" style="background: #2563eb; color: white;">추가</button>
        </div>
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
          <option value="user">user</option>
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
import { ref, onMounted } from 'vue'
import { getSites, createSite } from '../api/sites.js'
import { getUsers, createUser, deleteUser, resetPassword } from '../api/users.js'

const sites        = ref([])
const selectedSite = ref(null)
const users        = ref([])
const sitesLoading = ref(true)
const usersLoading = ref(false)

const showSiteForm  = ref(false)
const newSiteName   = ref('')
const siteFormError = ref(null)

const showUserForm  = ref(false)
const newUser       = ref({ username: '', role: 'user' })
const userFormError = ref(null)

const initialPassword = ref(null)

onMounted(async () => {
  try {
    sites.value = await getSites()
  } catch (e) {
    console.error('[AdminView] 현장 목록 로드 실패:', e)
  } finally {
    sitesLoading.value = false
  }
})

async function selectSite(site) {
  selectedSite.value = site
  usersLoading.value = true
  try {
    users.value = await getUsers(site.id)
  } catch (e) {
    console.error('[AdminView] 계정 목록 로드 실패:', e)
  } finally {
    usersLoading.value = false
  }
}

function openSiteForm() {
  newSiteName.value   = ''
  siteFormError.value = null
  showSiteForm.value  = true
}

async function handleCreateSite() {
  if (!newSiteName.value.trim()) return
  siteFormError.value = null
  try {
    const site = await createSite(newSiteName.value.trim())
    sites.value.push({ ...site, user_count: 0 })
    showSiteForm.value = false
    newSiteName.value  = ''
  } catch (e) {
    siteFormError.value = e.response?.data?.detail ?? e.message
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
    const res = await createUser(selectedSite.value.id, newUser.value)
    initialPassword.value = res.initial_password
    users.value.push(res.user)
    showUserForm.value = false
    // 현장 user_count 업데이트
    const idx = sites.value.findIndex(s => s.id === selectedSite.value.id)
    if (idx !== -1) sites.value[idx].user_count++
  } catch (e) {
    userFormError.value = e.response?.data?.detail ?? e.message
  }
}

async function handleDeleteUser(u) {
  if (!confirm(`${u.username} 계정을 삭제하시겠습니까?`)) return
  try {
    await deleteUser(selectedSite.value.id, u.id)
    users.value = users.value.filter(x => x.id !== u.id)
    const idx = sites.value.findIndex(s => s.id === selectedSite.value.id)
    if (idx !== -1) sites.value[idx].user_count = Math.max(0, sites.value[idx].user_count - 1)
  } catch (e) {
    alert(e.response?.data?.detail ?? e.message)
  }
}

async function handleResetPassword(u) {
  if (!confirm(`${u.username}의 비밀번호를 초기화하시겠습니까?`)) return
  try {
    const res = await resetPassword(selectedSite.value.id, u.id)
    initialPassword.value = res.new_password
  } catch (e) {
    alert(e.response?.data?.detail ?? e.message)
  }
}
</script>
