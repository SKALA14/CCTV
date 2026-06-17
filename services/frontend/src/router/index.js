// 라우트 정의 + 인증/권한 네비게이션 가드
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import DashboardView      from '../views/DashboardView.vue'
import SearchView         from '../views/SearchView.vue'
import ClipDetailView     from '../views/ClipDetailView.vue'
import ManualView         from '../views/ManualView.vue'
import LoginView          from '../views/LoginView.vue'
import AdminView          from '../views/AdminView.vue'
import PasswordChangeView from '../views/PasswordChangeView.vue'
import StatusView         from '../views/StatusView.vue'
import ProfileView        from '../views/ProfileView.vue'
import ReportView         from '../views/ReportView.vue'
import ZoneView           from '../views/ZoneView.vue'

const routes = [
    { path: '/login',           name: 'login',           component: LoginView,          meta: { public: true } },
    { path: '/',                redirect: '/wall' },
    { path: '/wall',            name: 'wall',             component: DashboardView,      meta: { bare: true } },
    { path: '/search',          name: 'search',           component: SearchView },
    { path: '/search/:id',      name: 'clip-detail',      component: ClipDetailView,    props: true },
    { path: '/zones',           name: 'zones',            component: ZoneView },
    { path: '/manual',          name: 'manual',           component: ManualView },
    { path: '/reports',         name: 'reports',          component: ReportView,         meta: { adminOnly: true } },
    { path: '/admin',           name: 'admin',            component: AdminView,          meta: { adminOnly: true } },
    { path: '/status',          name: 'status',           component: StatusView,         meta: { adminOnly: true } },
    { path: '/profile',         name: 'profile',          component: ProfileView },
    { path: '/password-change', name: 'password-change',  component: PasswordChangeView, meta: { bare: true } },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// 네비게이션 가드 — 비인증 접근 차단
router.beforeEach(async (to) => {
    if (to.meta.public) return true

    const auth = useAuthStore()

    if (!auth.initialized) {
        await auth.fetchMe()
    }

    if (!auth.isLoggedIn) {
        return { name: 'login' }
    }

    // 비밀번호 변경 강제: /password-change 외 모든 페이지 차단
    if (auth.mustChangePwd && to.name !== 'password-change') {
        return { name: 'password-change' }
    }

    // admin 전용 페이지 — 권한 없으면 관제(홈)로
    if (to.meta.adminOnly && !auth.isAdmin) {
        return { name: 'wall' }
    }

    return true
})

export default router
