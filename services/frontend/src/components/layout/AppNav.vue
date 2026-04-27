<template>
  <nav class="flex flex-col items-center gap-1 px-2">
    <router-link to="/" class="nav-tab" exact-active-class="active">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="7" height="7" rx="1.5"/>
        <rect x="14" y="3" width="7" height="7" rx="1.5"/>
        <rect x="3" y="14" width="7" height="7" rx="1.5"/>
        <rect x="14" y="14" width="7" height="7" rx="1.5"/>
      </svg>
      <span>메인</span>
    </router-link>

    <router-link to="/search" class="nav-tab" active-class="active">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="11" cy="11" r="7"/>
        <path d="m21 21-4.35-4.35" stroke-linecap="round"/>
      </svg>
      <span>검색</span>
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
  </nav>
</template>
