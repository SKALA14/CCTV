<!-- 관리 화면 — 자기 현장 계정 관리 (admin 전용) -->
<template>
  <div class="app-shell" :class="{ dark: isDark }">
    <!-- Top Navigation -->
    <header class="topnav">
      <div class="topnav-inner">
        <div class="topnav-actions topnav-actions-only">
          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '라이트 모드' : '다크 모드'">
            <i :class="isDark ? 'ri-sun-line' : 'ri-moon-line'"></i>
          </button>
          <router-link to="/profile" class="profile-nav-btn">
            <i class="ri-user-3-line"></i>
          </router-link>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Page Header -->
      <div class="page-header">
        <div class="page-header-icon">
          <i class="ri-admin-line"></i>
        </div>
        <div>
          <h1 class="page-title">Account Management</h1>
          <p class="page-desc">현장 계정을 추가하고, 비밀번호를 초기화하거나 삭제할 수 있습니다.</p>
        </div>
        <div class="page-header-actions">
          <button class="btn-refresh" @click="handleRefresh" :disabled="refreshing">
            <i :class="refreshing ? 'ri-loader-4-line spin-icon' : 'ri-refresh-line'"></i>
            <span>{{ refreshing ? '새로고침 중...' : '새로고침' }}</span>
          </button>
          <button class="btn-accent" @click="openUserForm">
            <i class="ri-add-line"></i> 계정 추가
          </button>
        </div>
      </div>

      <!-- Error Banner -->
      <div v-if="error" class="error-box">
        <i class="ri-error-warning-line"></i>
        <div>
          <p class="error-title">계정 정보를 불러오지 못했습니다</p>
          <p class="error-detail">{{ error }}</p>
          <button class="btn-ghost" @click="handleRefresh">다시 시도</button>
        </div>
      </div>

      <!-- Section Header -->
      <div class="section-header">
        <h2 class="section-title">
          <i class="ri-user-settings-line"></i> {{ siteName }} — 계정
        </h2>
        <span class="section-badge">{{ users.length }} users</span>
      </div>

      <!-- Loading -->
      <div v-if="usersLoading" class="card card-glow">
        <div class="loading-center">
          <span class="spinner spinner-accent"></span>
          <p>불러오는 중...</p>
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="users.length === 0" class="card card-glow">
        <div class="empty-mini">
          <i class="ri-user-line"></i>
          <span>등록된 계정이 없습니다</span>
        </div>
      </div>

      <!-- Account Table -->
      <div v-else class="card card-glow table-card">
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th class="th-main">username</th>
                <th class="th-sm">role</th>
                <th class="th-md">마지막 로그인</th>
                <th class="th-sm">상태</th>
                <th class="th-actions">작업</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td class="td-main">
                  {{ u.username }}
                  <span v-if="u.must_change_password" class="initial-badge">(초기)</span>
                </td>
                <td>
                  <span class="role-chip" :class="'role-' + u.role">{{ u.role }}</span>
                </td>
                <td class="td-muted td-mono">{{ formatTime(u.last_login) }}</td>
                <td>
                  <span class="account-status" :class="u.is_active ? 'account-active' : 'account-inactive'">
                    <span class="status-dot-sm"></span>
                    {{ u.is_active ? '활성' : '비활성' }}
                  </span>
                </td>
                <td class="td-actions">
                  <div class="action-btns">
                    <button class="btn-sm btn-warn" :disabled="loading" @click="handleResetPassword(u)">초기화</button>
                    <button v-if="u.role !== 'admin'" class="btn-sm btn-danger" :disabled="deleteLoading" @click="confirmDelete(u)">삭제</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>

    <!-- 계정 추가 모달 -->
    <div v-if="showUserForm" class="modal-overlay" @click.self="showUserForm = false">
      <div class="modal-panel modal-sm">
        <div class="modal-header">
          <div class="modal-header-left">
            <div class="modal-header-icon modal-header-icon-accent">
              <i class="ri-user-add-line"></i>
            </div>
            <h3 class="modal-title">계정 추가</h3>
          </div>
          <button class="modal-close" @click="showUserForm = false">
            <i class="ri-close-line"></i>
          </button>
        </div>
        <div class="modal-body modal-body-pad">
          <div class="form-group">
            <label class="form-label"><i class="ri-user-line"></i> username</label>
            <input
              v-model="newUser.username"
              type="text"
              placeholder="새 계정 username"
              class="form-input"
              autofocus
            />
          </div>
          <div class="form-group">
            <label class="form-label"><i class="ri-shield-user-line"></i> role</label>
            <select v-model="newUser.role" class="form-select">
              <option value="user">user — 조회·검색 (관제)</option>
              <option value="admin">admin — 콘솔 관리</option>
            </select>
          </div>
          <div v-if="userFormError" class="form-error">
            <i class="ri-error-warning-line"></i> {{ userFormError }}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-ghost" @click="showUserForm = false">취소</button>
          <button class="btn-accent" :disabled="!newUser.username.trim() || addLoading" @click="handleCreateUser">
            <span v-if="addLoading"><span class="spinner-inline"></span> 추가 중...</span>
            <span v-else>추가</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 삭제 확인 모달 -->
    <div v-if="deleteConfirm.open" class="modal-overlay" @click.self="deleteConfirm = { open: false, account: null }">
      <div class="modal-panel modal-xs">
        <div class="modal-body modal-body-pad modal-center">
          <div class="danger-icon-box">
            <i class="ri-delete-bin-line"></i>
          </div>
          <h3 class="modal-title">계정 삭제</h3>
          <p class="modal-desc">
            <strong>{{ deleteConfirm.account?.username }}</strong> 계정을 삭제하시겠습니까?<br>
            이 작업은 취소할 수 없습니다.
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn-ghost" @click="deleteConfirm = { open: false, account: null }">취소</button>
          <button class="btn-danger" :disabled="deleteLoading" @click="handleDeleteUser">
            <span v-if="deleteLoading"><span class="spinner-inline"></span> 삭제 중...</span>
            <span v-else>삭제</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 초기 비밀번호 표시 모달 -->
    <div v-if="passwordModal.open" class="modal-overlay" @click.self="passwordModal = { open: false, password: '', targetUsername: '' }">
      <div class="modal-panel modal-sm">
        <div class="modal-header">
          <div class="modal-header-left">
            <div class="modal-header-icon modal-header-icon-warn">
              <i class="ri-key-line"></i>
            </div>
            <h3 class="modal-title">초기 비밀번호</h3>
          </div>
          <button class="modal-close" @click="passwordModal = { open: false, password: '', targetUsername: '' }">
            <i class="ri-close-line"></i>
          </button>
        </div>
        <div class="modal-body modal-body-pad">
          <p class="modal-desc">
            <strong>{{ passwordModal.targetUsername }}</strong>의 초기 비밀번호입니다.<br>
            이 비밀번호는 지금만 표시됩니다. 담당자에게 안전하게 전달하세요.
          </p>
          <div class="password-display">
            <code>{{ passwordModal.password }}</code>
          </div>
        </div>
        <div class="modal-footer modal-footer-end">
          <button class="btn-accent" @click="passwordModal = { open: false, password: '', targetUsername: '' }">
            확인
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default { name: 'AdminView' }
</script>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getUsers, createUser, deleteUser, resetPassword } from '../api/users.js'
import { useAuthStore } from '../stores/authStore.js'
import { useTheme } from '../composables/useTheme.js'

const auth = useAuthStore()
const siteId   = computed(() => auth.user?.site_id)
const siteName = computed(() => auth.user?.site_name || '내 현장')

const { isDark, toggle: toggleTheme } = useTheme()

const users        = ref([])
const usersLoading = ref(true)
const error        = ref('')
const loading      = ref(false)
const refreshing   = ref(false)

onMounted(() => { loadUsers() })

async function loadUsers() {
  usersLoading.value = true
  error.value = ''
  try {
    users.value = await getUsers(siteId.value)
  } catch (e) {
    error.value = e.response?.data?.detail ?? e.message
  } finally {
    usersLoading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  await loadUsers()
  refreshing.value = false
}

const showUserForm  = ref(false)
const newUser       = ref({ username: '', role: 'user' })
const userFormError = ref(null)
const addLoading    = ref(false)

function openUserForm() {
  newUser.value       = { username: '', role: 'user' }
  userFormError.value = null
  showUserForm.value  = true
}

async function handleCreateUser() {
  if (!newUser.value.username.trim()) return
  addLoading.value = true
  userFormError.value = null
  try {
    const res = await createUser(siteId.value, newUser.value)
    users.value.push(res)
    showUserForm.value = false
    passwordModal.value = { open: true, password: res.initial_password, targetUsername: res.username }
  } catch (e) {
    userFormError.value = e.response?.data?.detail ?? e.message
  } finally {
    addLoading.value = false
  }
}

const deleteConfirm = ref({ open: false, account: null })
const deleteLoading = ref(false)

function confirmDelete(u) {
  deleteConfirm.value = { open: true, account: u }
}

async function handleDeleteUser() {
  if (!deleteConfirm.value.account) return
  deleteLoading.value = true
  try {
    await deleteUser(siteId.value, deleteConfirm.value.account.id)
    users.value = users.value.filter(x => x.id !== deleteConfirm.value.account.id)
    deleteConfirm.value = { open: false, account: null }
  } catch (e) {
    alert(e.response?.data?.detail ?? e.message)
  } finally {
    deleteLoading.value = false
  }
}

const passwordModal = ref({ open: false, password: '', targetUsername: '' })

async function handleResetPassword(u) {
  if (!confirm(`Reset password for ${u.username}?`)) return
  loading.value = true
  try {
    const res = await resetPassword(siteId.value, u.id)
    passwordModal.value = { open: true, password: res.new_password, targetUsername: u.username }
  } catch (e) {
    alert(e.response?.data?.detail ?? e.message)
  } finally {
    loading.value = false
  }
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
/* ══ Design Tokens ══ */
.app-shell {
  --c-bg:           #f9fafb;
  --c-bg-card:      #ffffff;
  --c-bg-elevated:  #f3f4f6;
  --c-border:       #e5e7eb;
  --c-border-light: #f0f0f0;
  --c-text:         #111827;
  --c-text-secondary: #4b5563;
  --c-text-muted:   #9ca3af;
  --c-accent:       #77942e;
  --c-accent-soft:  #eef2df;
  --c-accent-border:#b6c77a;
  --c-accent-hover: #64731e;
  --c-red:          #ef4444;
  --c-red-soft:     #fef2f2;
  --c-amber:        #f59e0b;
  --c-amber-soft:   #fffbeb;
  --c-blue-soft:    #eff6ff;
  --c-blue-text:    #3b82f6;
  --c-green:        #22c55e;
}

.app-shell.dark {
  --c-bg:           #111827;
  --c-bg-card:      #1a1f2e;
  --c-bg-elevated:  #1f2937;
  --c-border:       #2d3548;
  --c-border-light: #263040;
  --c-text:         #f3f4f6;
  --c-text-secondary: #9ca3af;
  --c-text-muted:   #6b7280;
  --c-accent-soft:  #263112;
  --c-accent-border:#4d6420;
  --c-red-soft:     #2d1215;
  --c-amber-soft:   #2d2010;
  --c-blue-soft:    #1a2540;
}

/* ══ Base ══ */
.app-shell {
  min-height: 100vh;
  background: var(--c-bg);
  color: var(--c-text);
  font-family: 'Pretendard Variable', Pretendard, -apple-system, system-ui, sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  transition: background 0.3s, color 0.3s;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
button { font-family: inherit; cursor: pointer; white-space: nowrap; }
input, select { font-family: inherit; }
i { display: inline-flex; align-items: center; justify-content: center; }

/* ══ Topnav ══ */
.topnav {
  position: sticky; top: 0; z-index: 50;
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border-light);
  backdrop-filter: blur(12px);
}
.topnav-inner {
  max-width: 1440px; margin: 0 auto; padding: 0 24px;
  min-height: 64px; display: flex; align-items: center; justify-content: space-between;
}
.topnav-brand { display: flex; align-items: center; gap: 8px; }
.brand-logo-icon { height: 30px; object-fit: contain; }
.brand-logo-text { height: 20px; object-fit: contain; }
.profile-nav-btn {
  display: flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 50%;
  color: var(--c-accent-hover); text-decoration: none;
  background: var(--c-accent-soft);
  border: 1px solid var(--c-accent-border);
  box-shadow: 0 4px 12px rgba(17, 24, 39, 0.06);
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}
.profile-nav-btn:hover { transform: translateY(-1px); background: color-mix(in srgb, var(--c-accent-soft) 78%, white); box-shadow: 0 8px 18px rgba(17, 24, 39, 0.08); }
.profile-nav-btn i { font-size: 18px; }
.brand-icon {
  width: 32px; height: 32px; border-radius: 10px;
  background: var(--c-accent); display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.brand-icon i { color: #fff; font-size: 16px; }
.brand-text { display: flex; flex-direction: column; }
.brand-title { font-size: 13px; font-weight: 700; color: var(--c-text); line-height: 1; }
.brand-sub   { font-size: 10px; color: var(--c-text-muted); line-height: 1; margin-top: 1px; }

.topnav-actions { display: flex; align-items: center; gap: 12px; }
.topnav-actions-only { margin-left: auto; }
.topnav-links { display: flex; gap: 4px; }
.nav-link {
  font-size: 12px; padding: 6px 12px; border-radius: 8px;
  color: var(--c-text-secondary); text-decoration: none; font-weight: 500; transition: all 0.15s;
}
.nav-link:hover { color: var(--c-text); background: var(--c-bg-elevated); }
.nav-link.active { background: var(--c-accent-soft); color: var(--c-accent-hover); font-weight: 600; }
.nav-divider { width: 1px; height: 20px; background: var(--c-border); }

.theme-toggle {
  width: 40px; height: 40px; border-radius: 10px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.theme-toggle:hover { background: var(--c-border); }
.theme-toggle i { font-size: 18px; color: var(--c-text-secondary); }

/* ══ Main ══ */
.main-content { max-width: 1440px; margin: 0 auto; padding: 24px; }

.page-header { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
.page-header-icon {
  width: 28px; height: 28px; border-radius: 8px; flex-shrink: 0;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
}
.page-header-icon i { color: var(--c-accent-hover); font-size: 14px; }
.page-title { font-size: 18px; font-weight: 700; color: var(--c-text); }
.page-desc  { font-size: 12px; color: var(--c-text-muted); margin-top: 2px; }
.page-header-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }

/* ══ Section Header ══ */
.section-header { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.section-title {
  font-size: 14px; font-weight: 600; color: var(--c-text);
  display: flex; align-items: center; gap: 6px;
}
.section-title i { color: var(--c-accent-hover); font-size: 14px; }
.section-badge {
  font-size: 11px; padding: 3px 10px; border-radius: 999px;
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  border: 1px solid var(--c-border); font-weight: 500;
}

/* ══ Card ══ */
.card {
  background: var(--c-bg-card); border: 1px solid var(--c-border-light);
  border-radius: 14px; padding: 20px; transition: background 0.3s, border 0.3s;
}
.card-glow { position: relative; overflow: hidden; }
.card-glow::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse at 50% 0%, rgba(132,204,22,0.05) 0%, transparent 70%);
}
.table-card { padding: 0; }

/* ══ Table ══ */
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table thead tr { background: var(--c-bg-elevated); }
.data-table th {
  text-align: left; padding: 10px 16px;
  font-size: 11px; font-weight: 600; color: var(--c-text-muted);
  text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap;
}
.data-table tbody tr { border-top: 1px solid var(--c-border-light); transition: background 0.15s; }
.data-table tbody tr:hover { background: var(--c-bg-elevated); }
.data-table td { padding: 11px 16px; }

.th-main    { width: 30%; }
.th-sm      { width: 14%; }
.th-md      { width: 22%; }
.th-actions { text-align: right; }

.td-main { color: var(--c-text); font-weight: 500; }
.td-muted { color: var(--c-text-muted); }
.td-mono  { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.td-actions { text-align: right; }

/* ══ Role Badge ══ */
.role-chip {
  display: inline-flex; padding: 3px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
}
.role-admin    { background: var(--c-red-soft);   color: var(--c-red); }
.role-operator { background: var(--c-amber-soft);  color: var(--c-amber); }
.role-user     { background: var(--c-blue-soft);   color: var(--c-blue-text); }

/* ══ Initial Badge ══ */
.initial-badge {
  display: inline-flex; margin-left: 6px; padding: 1px 6px; border-radius: 4px;
  font-size: 10px; font-weight: 600;
  background: var(--c-amber-soft); color: var(--c-amber); vertical-align: middle;
}

/* ══ Account Status ══ */
.account-status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; }
.status-dot-sm { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.account-active  { color: var(--c-green); }
.account-active  .status-dot-sm { background: var(--c-green); box-shadow: 0 0 6px rgba(34,197,94,0.4); }
.account-inactive { color: var(--c-text-muted); }
.account-inactive .status-dot-sm { background: var(--c-text-muted); }

/* ══ Action Buttons ══ */
.action-btns { display: flex; align-items: center; justify-content: flex-end; gap: 6px; }
.btn-sm {
  font-size: 12px; padding: 5px 12px; border-radius: 7px;
  font-weight: 500; transition: all 0.15s;
}
.btn-warn {
  border: 1px solid rgba(245,158,11,0.3); background: var(--c-amber-soft);
  color: var(--c-amber);
}
.btn-warn:hover:not(:disabled) { background: rgba(245,158,11,0.2); }
.btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }

/* ══ Buttons ══ */
.btn-accent {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 7px 14px; border-radius: 8px; border: none;
  background: var(--c-accent); color: #fff; font-weight: 600; transition: all 0.2s;
}
.btn-accent:hover:not(:disabled) { background: var(--c-accent-hover); }
.btn-accent:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-ghost {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 7px 14px; border-radius: 8px;
  border: 1px solid var(--c-border); background: var(--c-bg-elevated);
  color: var(--c-text-secondary); font-weight: 500; transition: all 0.2s;
}
.btn-ghost:hover { background: var(--c-border); color: var(--c-text); }

.btn-danger {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 7px 14px; border-radius: 8px; border: none;
  background: var(--c-red); color: #fff; font-weight: 600; transition: all 0.2s;
}
.btn-danger:hover:not(:disabled) { opacity: 0.85; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-refresh {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 6px 14px; border-radius: 8px;
  border: 1px solid var(--c-border); background: var(--c-bg-card);
  color: var(--c-text-secondary); font-weight: 500; transition: all 0.2s;
}
.btn-refresh:hover:not(:disabled) { background: var(--c-bg-elevated); color: var(--c-text); }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-refresh i { font-size: 13px; }
.spin-icon { animation: spin 0.8s linear infinite; }

/* ══ Modal ══ */
.modal-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.modal-panel {
  width: 100%; background: var(--c-bg-card);
  border: 1px solid var(--c-border); border-radius: 16px;
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
}
.modal-sm { max-width: 400px; }
.modal-xs { max-width: 320px; }

.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--c-border-light); flex-shrink: 0;
}
.modal-header-left { display: flex; align-items: center; gap: 10px; }
.modal-header-icon {
  width: 32px; height: 32px; border-radius: 9px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.modal-header-icon-accent { background: var(--c-accent-soft); }
.modal-header-icon-accent i { color: var(--c-accent-hover); font-size: 14px; }
.modal-header-icon-warn { background: var(--c-amber-soft); }
.modal-header-icon-warn i { color: var(--c-amber); font-size: 14px; }
.modal-title { font-size: 14px; font-weight: 600; color: var(--c-text); }

.modal-close {
  width: 30px; height: 30px; border-radius: 7px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.modal-close:hover { background: var(--c-border); }
.modal-close i { font-size: 14px; color: var(--c-text-secondary); }

.modal-body { padding: 0; }
.modal-body-pad { padding: 20px; display: flex; flex-direction: column; gap: 14px; }
.modal-center { align-items: center; text-align: center; }
.modal-desc { font-size: 13px; color: var(--c-text-secondary); line-height: 1.6; }

.modal-footer {
  display: flex; align-items: center; justify-content: flex-end; gap: 8px;
  padding: 14px 20px; border-top: 1px solid var(--c-border-light); flex-shrink: 0;
}
.modal-footer-end { justify-content: flex-end; }

/* ══ Form ══ */
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-label {
  font-size: 12px; font-weight: 600; color: var(--c-text-secondary);
  display: flex; align-items: center; gap: 4px;
}
.form-input, .form-select {
  width: 100%; padding: 9px 14px; border-radius: 10px;
  border: 1px solid var(--c-border); background: var(--c-bg-elevated);
  color: var(--c-text); font-size: 13px; outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.form-input:focus, .form-select:focus {
  border-color: var(--c-accent-border);
  box-shadow: 0 0 0 3px rgba(132,204,22,0.1);
}
.form-input::placeholder { color: var(--c-text-muted); }
.form-error {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 12px; border-radius: 8px;
  background: var(--c-red-soft); color: var(--c-red);
  border: 1px solid rgba(239,68,68,0.2); font-size: 12px;
}

/* ══ Danger Icon ══ */
.danger-icon-box {
  width: 48px; height: 48px; border-radius: 50%; margin-bottom: 4px;
  background: var(--c-red-soft); display: flex; align-items: center; justify-content: center;
}
.danger-icon-box i { color: var(--c-red); font-size: 20px; }

/* ══ Password Display ══ */
.password-display {
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
  border-radius: 10px; padding: 14px; text-align: center;
}
.password-display code {
  font-family: 'JetBrains Mono', monospace; font-size: 18px; font-weight: 700;
  letter-spacing: 0.08em; color: var(--c-text); user-select: all;
}

/* ══ Loading / Empty / Error ══ */
.loading-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 0; gap: 12px;
}
.loading-center p { font-size: 12px; color: var(--c-text-muted); }
.spinner-accent {
  display: inline-block; width: 28px; height: 28px;
  border: 3px solid var(--c-accent-soft); border-top-color: var(--c-accent);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
.spinner-inline {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.7s linear infinite; vertical-align: middle;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-mini {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 32px 0; gap: 6px;
}
.empty-mini i    { font-size: 20px; color: var(--c-text-muted); }
.empty-mini span { font-size: 12px; color: var(--c-text-muted); }

.error-box {
  display: flex; align-items: flex-start; gap: 12px; padding: 16px;
  border-radius: 12px; background: var(--c-red-soft); border: 1px solid rgba(239,68,68,0.2);
  margin-bottom: 16px;
}
.error-box i      { color: var(--c-red); font-size: 18px; margin-top: 1px; flex-shrink: 0; }
.error-title      { font-size: 13px; font-weight: 600; color: var(--c-red); margin-bottom: 4px; }
.error-detail     { font-size: 12px; color: var(--c-red); opacity: 0.8; margin-bottom: 8px; }

/* ══ Responsive ══ */
@media (max-width: 1024px) {
  .topnav-links { display: none; }
  .nav-divider  { display: none; }
  .page-desc    { display: none; }
}
</style>
