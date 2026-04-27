import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import SearchView from '../views/SearchView.vue'
import ClipDetailView from '../views/ClipDetailView.vue'
import ManualView from '../views/ManualView.vue'

const routes = [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/search', name: 'search', component: SearchView },
    {
        path: '/search/:id',
        name: 'clip-detail',
        component: ClipDetailView,
        props: true,
    },
    { path: '/manual', name: 'manual', component: ManualView },
]

export default createRouter({
    history: createWebHistory(),
    routes,
})