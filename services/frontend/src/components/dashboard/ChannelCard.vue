<template>
  <div class="channel-card" :class="{ 'alert-state': isAlert }">
    <!-- 상태 배지 -->
    <div class="status-badge" :class="isAlert ? 'badge-alert' : 'badge-ok'">
      <span class="status-dot"></span>
      {{ isAlert ? channel.event_type : '정상' }}
    </div>

    <!-- 영상 영역 -->
    <div class="video-area">
      <span class="text-sm select-none" style="color: var(--text-subtle);">라이브 영상 ({{ channel.id }})</span>
    </div>

    <!-- 호버 액션 -->
    <div class="hover-actions">
      <button class="hover-btn" @click.stop="$emit('edit', channel)">수정</button>
      <button class="hover-btn" @click.stop="$emit('remove', channel.id)">삭제</button>
    </div>

    <!-- 채널명 하단 띠 -->
    <div class="name-strip">{{ channel.name }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ channel: Object })
defineEmits(['edit', 'remove'])

const isAlert = computed(() => props.channel.status === 'alert')
</script>
