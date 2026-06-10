import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
<<<<<<< HEAD
import DashboardView  from '../views/DashboardView.vue'
import SearchView     from '../views/SearchView.vue'
import ClipDetailView from '../views/ClipDetailView.vue'
import ManualView     from '../views/ManualView.vue'
import LoginView      from '../views/LoginView.vue'
import SettingsView   from '../views/SettingsView.vue'

const routes = [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/',      name: 'dashboard',   component: DashboardView },
    { path: '/search', name: 'search',     component: SearchView },
    {
        path: '/search/:id',
        name: 'clip-detail',
        component: ClipDetailView,
        props: true,
    },
    { path: '/manual',   name: 'manual',   component: ManualView },
    { path: '/settings', name: 'settings', component: SettingsView },
=======
import DashboardView      from '../views/DashboardView.vue'
import SearchView         from '../views/SearchView.vue'
import ClipDetailView     from '../views/ClipDetailView.vue'
import ManualView         from '../views/ManualView.vue'
import LoginView          from '../views/LoginView.vue'
import AdminView          from '../views/AdminView.vue'
import PasswordChangeView from '../views/PasswordChangeView.vue'
import StatusView         from '../views/StatusView.vue'

const routes = [
    { path: '/login',           name: 'login',           component: LoginView,          meta: { public: true } },
    { path: '/',                name: 'dashboard',        component: DashboardView },
    { path: '/search',          name: 'search',           component: SearchView },
    { path: '/search/:id',      name: 'clip-detail',      component: ClipDetailView,    props: true },
    { path: '/manual',          name: 'manual',           component: ManualView },
    { path: '/admin',           name: 'admin',            component: AdminView,          meta: { superadminOnly: true } },
    { path: '/status',          name: 'status',           component: StatusView,         meta: { superadminOnly: true } },
    { path: '/password-change', name: 'password-change',  component: PasswordChangeView },
>>>>>>> dev1-woos
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// 네비게이션 가드 — 비인증 접근 차단
router.beforeEach(async (to) => {
<<<<<<< HEAD
    if (to.meta.public) return true  // 로그인 페이지는 항상 허용

    const auth = useAuthStore()

    // 아직 인증 상태를 모르면 서버에서 확인 (한 번만 실행)
=======
    if (to.meta.public) return true

    const auth = useAuthStore()

>>>>>>> dev1-woos
    if (!auth.initialized) {
        await auth.fetchMe()
    }

    if (!auth.isLoggedIn) {
        return { name: 'login' }
    }

<<<<<<< HEAD
=======
    // 비밀번호 변경 강제: /password-change 외 모든 페이지 차단
    if (auth.mustChangePwd && to.name !== 'password-change') {
        return { name: 'password-change' }
    }

    // superadmin 전용 페이지
    if (to.meta.superadminOnly && !auth.isSuperadmin) {
        return { name: 'dashboard' }
    }

>>>>>>> dev1-woos
    return true
})

export default router
