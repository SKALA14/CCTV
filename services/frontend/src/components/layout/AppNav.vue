<!-- 좌측 네비게이션 탭 -->
<template>
  <nav class="flex flex-col items-center gap-1 px-2">
    <router-link to="/search" class="nav-tab" active-class="active">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="11" cy="11" r="7"/>
        <path d="m21 21-4.35-4.35" stroke-linecap="round"/>
      </svg>
      <span>검색</span>
    </router-link>

    <router-link to="/zones" class="nav-tab" active-class="active">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>구역</span>
    </router-link>

    <router-link to="/manual" class="nav-tab" active-class="active">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13" stroke-linecap="round"/>
        <line x1="16" y1="17" x2="8" y2="17" stroke-linecap="round"/>
      </svg>
      <span>메뉴얼</span>
    </router-link>

    <!-- admin 전용 -->
    <template v-if="authStore.isAdmin">
      <div class="nav-divider"></div>

      <router-link to="/reports" class="nav-tab" active-class="active">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <line x1="6" y1="20" x2="6" y2="13" stroke-linecap="round"/>
          <line x1="12" y1="20" x2="12" y2="9" stroke-linecap="round"/>
          <line x1="18" y1="20" x2="18" y2="5" stroke-linecap="round"/>
        </svg>
        <span>리포트</span>
      </router-link>

      <router-link to="/status" class="nav-tab" active-class="active">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M3 3v18h18"/>
          <path d="M7 14l3-3 3 3 5-5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span>현황</span>
      </router-link>

      <router-link to="/admin" class="nav-tab" active-class="active">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 00-3-3.87"/>
          <path d="M16 3.13a4 4 0 010 7.75"/>
        </svg>
        <span>관리</span>
      </router-link>
    </template>
  </nav>
</template>

<script setup>
import { useAuthStore } from '../../stores/authStore.js'
const authStore = useAuthStore()
</script>
