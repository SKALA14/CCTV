<template>
  <div class="dashboard-root" :class="{ dark: isDark }">
    <div class="ambient-bg"></div>
    <div class="ambient-radial"></div>

    <header class="dashboard-header">
      <div class="header-left">
        <div class="logo-group">
          <img src="/pic.png" alt="SIREN" class="brand-mark" />
          <img src="/letter.png" alt="SIREN" class="brand-wordmark" />
        </div>
        <span class="status-pill">
          <span class="status-dot" :class="{ active: activeCount > 0 }"></span>
          <span class="status-text">{{ activeCount }} / 4 채널 활성</span>
        </span>
      </div>
      <div class="header-center">{{ clock }}</div>
      <div class="header-right">
        <button class="header-btn" @click="openConsole">
          <i class="ri-settings-3-line"></i><span class="btn-label">콘솔</span>
        </button>
        <button class="header-btn" :class="{ active: panelOpen }" @click="panelOpen = !panelOpen">
          <i class="ri-notification-3-line"></i><span class="btn-label">알림</span>
          <span v-if="historyCount > 0" class="notif-badge">{{ historyCount }}</span>
        </button>
      </div>
    </header>

    <div class="main-body">
      <div class="channel-grid">
        <div v-for="slotIndex in [0,1,2,3]" :key="slotIndex" class="slot-wrapper">
          <ChannelCard
            v-if="slots[slotIndex]"
            :channel="slots[slotIndex]"
            :can-edit="canEdit"
            @edit="openEditModal"
            @remove="handleRemove"
          />
          <div v-else class="empty-slot" @click="canEdit && openAddModal(slotIndex)">
            <div class="empty-icon"><i class="ri-add-line"></i></div>
            <p class="empty-title">{{ canEdit ? '채널 추가' : '채널 없음' }}</p>
            <p class="empty-desc">{{ canEdit ? '클릭하여 채널을 등록하세요' : '관리자에게 문의하세요' }}</p>
          </div>
        </div>
      </div>

      <div v-if="panelOpen" class="event-panel">
        <div class="panel-header">
          <div class="panel-title-group">
            <div class="panel-icon"><i class="ri-notification-3-line"></i></div>
            <h3 class="panel-title">알림 내역</h3>
            <span v-if="unreadCount > 0" class="panel-count">{{ unreadCount }}</span>
          </div>
          <button class="panel-close" @click="panelOpen = false"><i class="ri-close-line"></i></button>
        </div>
        <div class="panel-list">
          <div v-if="filteredEvents.length === 0" class="panel-empty">
            <div class="empty-icon-box"><i class="ri-check-line"></i></div>
            <p class="empty-title">모든 알림을 확인했습니다</p>
            <p class="empty-desc">새로운 알림이 발생하면 여기에 표시됩니다</p>
          </div>
          <div v-else class="events-list">
            <div v-for="event in filteredEvents" :key="event._notifId" class="event-item" :class="['unread', getSeverityClass(event)]">
              <div class="event-dot" :class="getSeverityClass(event)"></div>
              <div class="event-body">
                <div class="event-header">
                  <p class="event-channel">{{ resolveChannelName(event) }}</p>
                  <span class="event-time">{{ formatTs(event.timestamp) }}</span>
                </div>
                <p class="event-message" :class="getSeverityClass(event)">{{ resolveMessage(event) }}</p>
                <div class="event-tags">
                  <span class="pipeline-tag" :class="event.pipeline === 'emergency' ? 'tag-emg' : 'tag-vlm'">
                    {{ event.pipeline === 'emergency' ? 'EMERGENCY' : 'VLM' }}
                  </span>
                  <span class="danger-tag" :class="'tag-' + event.danger_level">
                    {{ dangerLabel(event.danger_level) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="panel-footer"><p>{{ events.length }}개의 알림 중 {{ unreadCount }}개 미확인</p></div>
      </div>
    </div>

    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal-card">
        <div class="modal-head">
          <div>
            <h3 class="modal-title">{{ editingChannel ? `슬롯 ${activeSlot}에 채널 수정` : `슬롯 ${activeSlot}에 채널 등록` }}</h3>
            <p class="modal-cam-id">camera_id: cam{{ activeSlot }}</p>
          </div>
          <button class="modal-close" @click="closeModal"><i class="ri-close-line"></i></button>
        </div>

        <div class="modal-body">
          <div v-if="error" class="form-error"><i class="ri-error-warning-line"></i><p>{{ error }}</p></div>

          <div class="form-group">
            <label>채널명 <span class="required">*</span></label>
            <input v-model="formData.name" type="text" class="form-input" placeholder="예: 정문 CCTV" />
          </div>

          <div class="form-group">
            <label>소스 타입</label>
            <div class="source-toggle">
              <button type="button" :class="['toggle-btn', { active: formData.sourceType === 'url' }]" @click="formData.sourceType = 'url'">소스 URL</button>
              <button type="button" :class="['toggle-btn', { active: formData.sourceType === 'webcam' }]" @click="formData.sourceType = 'webcam'">웹캠</button>
            </div>
          </div>

          <div v-if="formData.sourceType === 'url'" class="form-group">
            <input v-model="formData.rtspUrl" type="text" class="form-input" placeholder="rtsp://192.168.x.x:554/stream 또는 http://..." />
          </div>

          <div class="form-group">
            <label>구역</label>
            <div class="select-wrap">
              <select v-model="formData.zone" class="form-select">
                <option value="">없음</option>
                <option v-for="z in zones" :key="z" :value="z">{{ z }}</option>
              </select>
              <i class="ri-arrow-down-s-line select-arrow"></i>
            </div>
          </div>
        </div>

        <div class="modal-divider"></div>

        <div class="modal-footer">
          <button type="button" class="btn-cancel" @click="closeModal">취소</button>
          <button type="button" class="btn-save" :disabled="submitting" @click="handleSubmit">
            {{ submitting ? '저장 중...' : '저장' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import { useEventStore } from '../stores/eventStore.js'
import { useChannels } from '../composables/useChannels.js'
import { postChannel, putChannel, deleteChannel } from '../api/channels.js'
import { fetchZones } from '../api/manuals.js'
import { detectSourceType } from '../utils/detectSourceType.js'
import ChannelCard from '../components/dashboard/ChannelCard.vue'
import { useTheme } from '../composables/useTheme.js'

const { isDark } = useTheme()
const router = useRouter()
const authStore = useAuthStore()
const { slots, addChannel, updateChannel, removeChannel } = useChannels()
const eventStore = useEventStore()

const canEdit = computed(() => authStore.user?.role === 'admin')
const activeCount = computed(() => slots.value.filter(Boolean).length)
const historyCount = computed(() => eventStore.notifHistory.length)
const panelOpen = ref(false)

const clock = ref('')
let clockTimer = null
function updateClock() { clock.value = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) }
onMounted(() => { updateClock(); clockTimer = setInterval(updateClock, 1000) })
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })

const showModal = ref(false)
const editingChannel = ref(null)
const activeSlot = ref(0)
const error = ref('')
const submitting = ref(false)
const zones = ref([])

const formData = ref({ name: '', sourceType: 'url', rtspUrl: '', zone: '' })

function openConsole() { window.open('/search', 'cctv-console', 'width=1440,height=900,left=120,top=80') }
function handleLogout() { localStorage.removeItem('auth_token'); localStorage.removeItem('auth_user'); router.push('/login') }

async function openAddModal(slot) {
  activeSlot.value = slot
  editingChannel.value = null
  formData.value = { name: '', sourceType: 'url', rtspUrl: '', zone: '' }
  error.value = ''
  showModal.value = true
  zones.value = await fetchZones().catch(() => [])
}

async function openEditModal(channel) {
  activeSlot.value = channel.slot
  editingChannel.value = channel
  formData.value = {
    name: channel.name || '',
    sourceType: channel.sourceType === 'webcam' ? 'webcam' : 'url',
    rtspUrl: channel.rtspUrl || '',
    zone: channel.zone || '',
  }
  error.value = ''
  showModal.value = true
  zones.value = await fetchZones().catch(() => [])
}

function closeModal() { showModal.value = false; editingChannel.value = null; error.value = '' }

async function handleSubmit() {
  error.value = ''
  if (!formData.value.name.trim()) { error.value = '채널명을 입력하세요.'; return }
  if (formData.value.sourceType === 'url' && !formData.value.rtspUrl.trim()) { error.value = '소스 URL을 입력하세요.'; return }

  submitting.value = true
  try {
    const isWebcam = formData.value.sourceType === 'webcam'
    const trimmedUrl = formData.value.rtspUrl.trim()
    const channelName = `cam${activeSlot.value}`
    const payload = {
      slot:        activeSlot.value,
      name:        formData.value.name.trim(),
      channelName,
      url:         isWebcam ? 'webcam' : trimmedUrl,
      rtspUrl:     isWebcam ? null : trimmedUrl,
      sourceType:  isWebcam ? 'webcam' : detectSourceType(trimmedUrl),
      description: '',
      options:     [],
      zone:        formData.value.zone || '',
    }

    if (editingChannel.value) {
      updateChannel(activeSlot.value, { ...payload })
      putChannel(channelName, payload).catch(console.error)
    } else {
      const res = await postChannel(payload)
      addChannel(activeSlot.value, {
        ...payload,
        ingestion_url: res?.ingestion_url || null,
        mtxPath:       res?.mtxPath       || null,
      })
    }
    closeModal()
  } catch (e) {
    error.value = e?.response?.data?.detail || '채널 등록에 실패했습니다.'
  } finally {
    submitting.value = false
  }
}

function handleRemove(slot) {
  if (confirm('채널을 삭제하시겠습니까?')) {
    const ch = slots.value[slot]
    removeChannel(slot)
    if (ch) deleteChannel(`cam${slot}`).catch(console.error)
  }
}

const events = computed(() => eventStore.notifHistory)
const unreadCount = computed(() => events.value.length)
const filteredEvents = computed(() => events.value)

function getSeverityClass(e) {
  const l = e.danger_level
  if (l === 'critical') return 'danger'
  if (l === 'high' || l === 'low') return 'warning'
  return 'info'
}

const EVENT_TYPE_LABEL = {
  fire: '화재 감지', smoke: '연기 감지', fall: '낙상 감지',
  fight: '폭력 감지', violence: '폭력 감지', intrusion: '침입 감지',
  unauthorized: '무단 침입', normal: '정상',
}
function formatEventLabel(type) { return EVENT_TYPE_LABEL[type] || type || '이벤트' }

function formatTs(ts) {
  if (!ts) return ''
  const n = Number(ts)
  const d = isNaN(n) ? new Date(ts) : new Date(n < 1e12 ? n * 1000 : n)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function resolveChannelName(event) {
  const cameraId = String(event.channel_id || event.camera_id || '')
  const ch = slots.value.find(c => c && String(c.camera_id || c.channelName || '') === cameraId)
  return ch?.name || event.channel_name || cameraId || '알 수 없음'
}

function resolveMessage(event) {
  if (event.pipeline === 'emergency') {
    const type = String(event.event_type || '').toLowerCase()
    if (type === 'fallen') return '작업자 낙상 감지'
    if (type === 'fire' || type === 'smoke') return '화재 위험 감지'
  }
  return event.reason || event.description || formatEventLabel(event.event_type) || '이상 상황이 감지되었습니다.'
}

function dangerLabel(level) {
  const map = { critical: '심각', high: '높음', low: '낮음', none: '정상' }
  return map[level] || (level || '').toUpperCase()
}
</script>

<style scoped>
/* ── Base ── */
.dashboard-root {
  --c-accent: #77942e;
  --c-accent-soft: #eef2df;
  --c-accent-border: #b6c77a;
  --c-accent-hover: #64731e;
  --c-accent-soft-dark: #263112;
  --c-accent-border-dark: #4d6420;
  height: 100vh; display: flex; flex-direction: column; overflow: hidden; background: #f9fafb; position: relative; font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
.ambient-bg, .ambient-radial { display: none; }

/* ── Header ── */
.dashboard-header { position: relative; z-index: 10; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; height: 56px; flex-shrink: 0; background: #ffffff; border-bottom: 1px solid #e5e7eb; }
.header-left { display: flex; align-items: center; gap: 16px; }
.logo-group { display: flex; align-items: center; gap: 10px; }
.brand-mark { width: 30px; height: 30px; object-fit: contain; display: block; flex-shrink: 0; }
.brand-wordmark { height: 20px; width: auto; object-fit: contain; display: block; flex-shrink: 0; }
.status-pill { display: none; align-items: center; gap: 8px; font-size: 12px; padding: 6px 12px; border-radius: 9999px; background: #f3f4f6; border: 1px solid #e5e7eb; }
@media (min-width: 640px) { .status-pill { display: flex; } }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #d1d5db; }
.status-dot.active { background: #77942e; animation: pulse 2s ease-in-out infinite; }
.status-text { color: #4b5563; font-weight: 500; }
.header-center { font-size: 13px; font-family: 'SF Mono', 'Fira Code', monospace; color: #9ca3af; letter-spacing: 0.05em; }
.header-right { display: flex; align-items: center; gap: 8px; }
.header-btn { display: flex; align-items: center; gap: 6px; padding: 8px 12px; border-radius: 9999px; font-size: 12px; color: #4b5563; background: transparent; border: 1px solid transparent; cursor: pointer; transition: all 0.2s ease; font-weight: 500; }
.header-btn:hover { color: #111827; background: #f3f4f6; border-color: #e5e7eb; }
.header-btn.active { color: var(--c-accent-hover); background: var(--c-accent-soft); border-color: var(--c-accent-border); }
.header-btn i { font-size: 14px; }
.btn-label { display: none; }
@media (min-width: 640px) { .btn-label { display: inline; } }
.notif-badge { font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 9999px; background: rgba(239, 68, 68, 0.10); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.25); }

/* ── Main ── */
.main-body { flex: 1; min-height: 0; position: relative; padding: 12px; z-index: 10; }
@media (min-width: 768px) { .main-body { padding: 16px; } }

.channel-grid { height: 100%; display: grid; grid-template-columns: 1fr; grid-auto-rows: 1fr; gap: 12px; }
@media (min-width: 1024px) { .channel-grid { grid-template-columns: 1fr 1fr; gap: 16px; } }
.slot-wrapper { min-height: 0; height: 100%; }

/* ── Empty slot ── */
.empty-slot { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 20px; border: 2px dashed #d1d5db; background: #ffffff; transition: all 0.3s ease; cursor: pointer; }
.empty-slot:hover { border-color: var(--c-accent); background: #f7f9ee; }
.empty-icon { width: 64px; height: 64px; border-radius: 16px; display: flex; align-items: center; justify-content: center; background: #f3f4f6; border: 1px solid #e5e7eb; transition: all 0.3s ease; }
.empty-slot:hover .empty-icon { background: var(--c-accent-soft); border-color: var(--c-accent-border); }
.empty-icon i { font-size: 24px; color: #9ca3af; transition: all 0.3s ease; }
.empty-slot:hover .empty-icon i { color: var(--c-accent); }
.empty-title { margin-top: 16px; font-size: 14px; font-weight: 500; color: #4b5563; transition: color 0.3s ease; }
.empty-slot:hover .empty-title { color: #111827; }
.empty-desc { margin-top: 4px; font-size: 12px; color: #9ca3af; }

/* ── Notification panel ── */
.event-panel { position: absolute; top: 12px; right: 12px; bottom: 12px; width: 320px; z-index: 20; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 20px; display: flex; flex-direction: column; overflow: hidden; animation: slideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08); }
@media (min-width: 768px) { .event-panel { top: 16px; right: 16px; bottom: 16px; } }
@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

.panel-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #f3f4f6; }
.panel-title-group { display: flex; align-items: center; gap: 10px; }
.panel-icon { width: 32px; height: 32px; border-radius: 10px; background: var(--c-accent-soft); border: 1px solid var(--c-accent-border); display: flex; align-items: center; justify-content: center; }
.panel-icon i { font-size: 14px; color: var(--c-accent-hover); }
.panel-title { font-size: 14px; font-weight: 600; color: #111827; }
.panel-count { font-size: 12px; color: #4b5563; background: #f3f4f6; border-radius: 9999px; padding: 2px 10px; border: 1px solid #e5e7eb; }
.panel-close { width: 32px; height: 32px; border-radius: 50%; border: 1px solid #e5e7eb; background: transparent; display: flex; align-items: center; justify-content: center; color: #9ca3af; cursor: pointer; transition: all 0.2s ease; }
.panel-close:hover { background: #f3f4f6; color: #111827; }
.panel-close i { font-size: 14px; }

.panel-list { flex: 1; overflow-y: auto; padding: 8px 12px; }
.panel-list::-webkit-scrollbar { width: 4px; }
.panel-list::-webkit-scrollbar-track { background: transparent; }
.panel-list::-webkit-scrollbar-thumb { background: #e5e7eb; border-radius: 999px; }

.panel-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 64px 0; text-align: center; }
.empty-icon-box { width: 56px; height: 56px; border-radius: 16px; background: var(--c-accent-soft); border: 1px solid var(--c-accent-border); display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }
.empty-icon-box i { font-size: 20px; color: var(--c-accent); }
.panel-empty .empty-title { font-size: 14px; font-weight: 500; color: #4b5563; margin: 0; }
.panel-empty .empty-desc { font-size: 12px; color: #9ca3af; margin-top: 6px; }

.events-list { display: flex; flex-direction: column; gap: 6px; }
.event-item { padding: 12px 14px; border-radius: 12px; border: 1px solid #f3f4f6; transition: all 0.15s ease; display: flex; align-items: flex-start; gap: 10px; background: #f9fafb; }
.event-item:hover { border-color: #e5e7eb; background: #ffffff; }
.event-item.danger { border-color: rgba(239, 68, 68, 0.25); background: #fff5f5; }
.event-item.warning { border-color: var(--c-accent-border); background: #f7f9ee; }

.event-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
.event-dot.danger { background: #ef4444; }
.event-dot.warning { background: var(--c-accent); }
.event-dot.info { background: #d1d5db; }

.event-body { flex: 1; min-width: 0; }
.event-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.event-channel { font-size: 12px; font-weight: 600; color: #111827; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.event-time { font-size: 10px; color: #9ca3af; flex-shrink: 0; font-family: 'SF Mono', monospace; }
.event-message { font-size: 12px; margin-top: 3px; margin-bottom: 0; }
.event-message.danger { color: #ef4444; }
.event-message.warning { color: var(--c-accent-hover); }
.event-message.info { color: #6b7280; }

.event-tags { display: flex; align-items: center; gap: 5px; margin-top: 6px; flex-wrap: wrap; }
.pipeline-tag { font-size: 9px; font-weight: 700; letter-spacing: 0.06em; padding: 2px 6px; border-radius: 4px; }
.tag-emg { background: rgba(220,38,38,0.12); color: #dc2626; }
.tag-vlm { background: rgba(245,158,11,0.12); color: #d97706; }
.danger-tag { font-size: 9px; font-weight: 700; letter-spacing: 0.04em; padding: 2px 6px; border-radius: 4px; }
.tag-critical { background: rgba(220,38,38,0.12); color: #dc2626; }
.tag-high { background: rgba(245,158,11,0.12); color: #d97706; }
.tag-low { background: rgba(119,148,46,0.12); color: var(--c-accent-hover); }
.tag-none { background: #f3f4f6; color: #9ca3af; }

.panel-footer { padding: 12px 20px; border-top: 1px solid #f3f4f6; text-align: center; }
.panel-footer p { font-size: 11px; color: #9ca3af; margin: 0; }

/* ── Modal ── */
.modal-overlay { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.35); backdrop-filter: blur(6px); animation: fadeIn 0.2s ease-out forwards; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { transform: scale(0.96); opacity: 0; } to { transform: scale(1); opacity: 1; } }

.modal-card { width: 100%; max-width: 460px; margin: 0 16px; background: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.12); border: 1px solid #e5e7eb; animation: scaleIn 0.25s cubic-bezier(0.16, 1, 0.3, 1) forwards; }

.modal-head { display: flex; align-items: flex-start; justify-content: space-between; padding: 24px 24px 0; }
.modal-title { font-size: 17px; font-weight: 700; color: #111827; margin: 0 0 4px; }
.modal-cam-id { font-size: 12px; color: #9ca3af; margin: 0; }
.modal-close { width: 32px; height: 32px; flex-shrink: 0; border-radius: 50%; border: 1px solid #e5e7eb; background: transparent; display: flex; align-items: center; justify-content: center; color: #9ca3af; cursor: pointer; transition: all 0.15s ease; }
.modal-close:hover { background: #f3f4f6; color: #111827; }
.modal-close i { font-size: 16px; }

.modal-body { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 13px; font-weight: 600; color: #374151; }
.required { color: #ef4444; }

.form-input { width: 100%; padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 14px; color: #111827; background: #ffffff; outline: none; transition: all 0.15s ease; box-sizing: border-box; }
.form-input::placeholder { color: #9ca3af; }
.form-input:focus { border-color: var(--c-accent); box-shadow: 0 0 0 3px rgba(119, 148, 46, 0.15); }

.source-toggle { display: flex; border: 1px solid #d1d5db; border-radius: 10px; overflow: hidden; }
.toggle-btn { flex: 1; padding: 10px 16px; font-size: 13px; font-weight: 500; color: #6b7280; background: #ffffff; border: none; cursor: pointer; transition: all 0.15s ease; }
.toggle-btn.active { background: var(--c-accent); color: #ffffff; }
.toggle-btn:not(.active):hover { background: #f9fafb; color: #111827; }

.select-wrap { position: relative; }
.form-select { width: 100%; padding: 10px 40px 10px 14px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 14px; color: #111827; background: #ffffff; appearance: none; outline: none; cursor: pointer; transition: all 0.15s ease; box-sizing: border-box; }
.form-select:focus { border-color: var(--c-accent); box-shadow: 0 0 0 3px rgba(119, 148, 46, 0.15); }
.select-arrow { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); font-size: 16px; color: #9ca3af; pointer-events: none; }

.form-error { display: flex; align-items: center; gap: 8px; background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 10px; padding: 10px 14px; }
.form-error i { font-size: 14px; color: #ef4444; flex-shrink: 0; }
.form-error p { font-size: 13px; color: #ef4444; margin: 0; }

.modal-divider { height: 1px; background: #f3f4f6; }

.modal-footer { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding: 16px 24px; }
.btn-cancel { padding: 10px 20px; border-radius: 10px; border: 1px solid #d1d5db; background: #ffffff; font-size: 14px; font-weight: 500; color: #374151; cursor: pointer; transition: all 0.15s ease; }
.btn-cancel:hover { background: #f3f4f6; }
.btn-save { padding: 10px 20px; border-radius: 10px; border: none; background: var(--c-accent); font-size: 14px; font-weight: 600; color: #ffffff; cursor: pointer; transition: all 0.15s ease; }
.btn-save:hover:not(:disabled) { background: var(--c-accent-hover); }
.btn-save:disabled { background: #dbe6bd; color: var(--c-accent-hover); cursor: not-allowed; }

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

/* ── Dark mode ── */
.dashboard-root.dark { background: #111827; }
.dashboard-root.dark .dashboard-header { background: #1a1f2e; border-bottom-color: #2d3548; }
.dashboard-root.dark .brand-mark { filter: brightness(0) invert(1); }
.dashboard-root.dark .status-pill { background: #1f2937; border-color: #2d3548; }
.dashboard-root.dark .status-text { color: #9ca3af; }
.dashboard-root.dark .status-dot { background: #374151; }
.dashboard-root.dark .status-dot.active { background: #77942e; }
.dashboard-root.dark .header-center { color: #4b5563; }
.dashboard-root.dark .header-btn { color: #9ca3af; }
.dashboard-root.dark .header-btn:hover { color: #f3f4f6; background: #1f2937; border-color: #2d3548; }
.dashboard-root.dark .header-btn.active { color: #c7d99a; background: var(--c-accent-soft-dark); border-color: var(--c-accent-border-dark); }
.dashboard-root.dark .notif-badge { background: rgba(239,68,68,0.15); color: #fca5a5; border-color: rgba(239,68,68,0.30); }

.dashboard-root.dark .empty-slot { background: #1a1f2e; border-color: #2d3548; }
.dashboard-root.dark .empty-slot:hover { border-color: var(--c-accent); background: var(--c-accent-soft-dark); }
.dashboard-root.dark .empty-icon { background: #1f2937; border-color: #2d3548; }
.dashboard-root.dark .empty-slot:hover .empty-icon { background: var(--c-accent-soft-dark); border-color: var(--c-accent-border-dark); }
.dashboard-root.dark .empty-icon i { color: #4b5563; }
.dashboard-root.dark .empty-slot:hover .empty-icon i { color: var(--c-accent); }
.dashboard-root.dark .empty-title { color: #9ca3af; }
.dashboard-root.dark .empty-slot:hover .empty-title { color: #f3f4f6; }
.dashboard-root.dark .empty-desc { color: #4b5563; }

.dashboard-root.dark .event-panel { background: #1a1f2e; border-color: #2d3548; box-shadow: 0 4px 24px rgba(0,0,0,0.40); }
.dashboard-root.dark .panel-header { border-bottom-color: #263040; }
.dashboard-root.dark .panel-icon { background: var(--c-accent-soft-dark); border-color: var(--c-accent-border-dark); }
.dashboard-root.dark .panel-icon i { color: #c7d99a; }
.dashboard-root.dark .panel-title { color: #f3f4f6; }
.dashboard-root.dark .panel-count { background: #1f2937; border-color: #2d3548; color: #9ca3af; }
.dashboard-root.dark .panel-close { border-color: #2d3548; color: #6b7280; }
.dashboard-root.dark .panel-close:hover { background: #1f2937; color: #f3f4f6; }
.dashboard-root.dark .panel-list::-webkit-scrollbar-thumb { background: #2d3548; }
.dashboard-root.dark .empty-icon-box { background: var(--c-accent-soft-dark); border-color: var(--c-accent-border-dark); }
.dashboard-root.dark .empty-icon-box i { color: var(--c-accent); }
.dashboard-root.dark .panel-empty .empty-title { color: #9ca3af; }
.dashboard-root.dark .panel-empty .empty-desc { color: #4b5563; }

.dashboard-root.dark .event-item { background: #1f2937; border-color: #263040; }
.dashboard-root.dark .event-item:hover { background: #1a1f2e; border-color: #2d3548; }
.dashboard-root.dark .event-item.danger { border-color: rgba(239,68,68,0.30); background: rgba(127,29,29,0.20); }
.dashboard-root.dark .event-item.warning { border-color: var(--c-accent-border-dark); background: var(--c-accent-soft-dark); }
.dashboard-root.dark .event-channel { color: #f3f4f6; }
.dashboard-root.dark .event-time { color: #4b5563; }
.dashboard-root.dark .event-message.warning { color: #c7d99a; }
.dashboard-root.dark .event-message.info { color: #6b7280; }
.dashboard-root.dark .tag-emg { background: rgba(220,38,38,0.18); color: #f87171; }
.dashboard-root.dark .tag-vlm { background: rgba(245,158,11,0.18); color: #fbbf24; }
.dashboard-root.dark .tag-critical { background: rgba(220,38,38,0.18); color: #f87171; }
.dashboard-root.dark .tag-high { background: rgba(245,158,11,0.18); color: #fbbf24; }
.dashboard-root.dark .tag-low { background: rgba(119,148,46,0.2); color: #c7d99a; }
.dashboard-root.dark .tag-none { background: #1f2937; color: #4b5563; }
.dashboard-root.dark .panel-footer { border-top-color: #263040; }
.dashboard-root.dark .panel-footer p { color: #4b5563; }

.dashboard-root.dark .modal-overlay { background: rgba(0,0,0,0.60); }
.dashboard-root.dark .modal-card { background: #1a1f2e; border-color: #2d3548; }
.dashboard-root.dark .modal-title { color: #f3f4f6; }
.dashboard-root.dark .modal-cam-id { color: #6b7280; }
.dashboard-root.dark .modal-close { border-color: #2d3548; color: #6b7280; }
.dashboard-root.dark .modal-close:hover { background: #1f2937; color: #f3f4f6; }
.dashboard-root.dark .form-group label { color: #d1d5db; }
.dashboard-root.dark .form-input { background: #1f2937; border-color: #2d3548; color: #f3f4f6; }
.dashboard-root.dark .form-input::placeholder { color: #4b5563; }
.dashboard-root.dark .form-input:focus { border-color: var(--c-accent); background: #1a1f2e; box-shadow: 0 0 0 3px rgba(119,148,46,0.12); }
.dashboard-root.dark .source-toggle { border-color: #2d3548; }
.dashboard-root.dark .toggle-btn { background: #1f2937; color: #6b7280; }
.dashboard-root.dark .toggle-btn:not(.active):hover { background: #263040; color: #f3f4f6; }
.dashboard-root.dark .form-select { background: #1f2937; border-color: #2d3548; color: #f3f4f6; }
.dashboard-root.dark .form-select:focus { border-color: var(--c-accent); background: #1a1f2e; box-shadow: 0 0 0 3px rgba(119,148,46,0.12); }
.dashboard-root.dark .select-arrow { color: #4b5563; }
.dashboard-root.dark .modal-divider { background: #263040; }
.dashboard-root.dark .btn-cancel { background: #1f2937; border-color: #2d3548; color: #d1d5db; }
.dashboard-root.dark .btn-cancel:hover { background: #263040; }
</style>
