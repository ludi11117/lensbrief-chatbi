import { createRouter, createWebHistory } from 'vue-router'
import { hasGrant, restoreUser, user } from './auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/reports' },
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue') },
    { path: '/reports', name: 'reports', meta: { grant: 'report.read', label: '报告中心' }, component: () => import('./views/ReportsView.vue') },
    { path: '/reports/new', name: 'create', meta: { grant: 'report.create', label: '新建报告' }, component: () => import('./views/ReportFormView.vue') },
    { path: '/reports/:id', name: 'report', meta: { label: '报告详情' }, component: () => import('./views/ReportView.vue') },
    { path: '/reports/:id/edit', name: 'edit', meta: { grant: 'report.edit', label: '编辑报告' }, component: () => import('./views/ReportFormView.vue') },
    { path: '/files/:asset', name: 'asset', meta: { label: '文件预览' }, component: () => import('./views/AssetView.vue') },
    { path: '/queries', name: 'queries', meta: { grant: 'query.read', label: '查询记录' }, component: () => import('./views/QueriesView.vue') },
    { path: '/access', name: 'access', meta: { grant: 'user.manage', label: '权限管理' }, component: () => import('./views/AccessView.vue') },
    { path: '/:pathMatch(.*)*', name: 'missing', meta: { label: '页面不存在' }, component: () => import('./views/NoticeView.vue') },
  ],
})
router.beforeEach(async (to) => {
  await restoreUser()
  if (to.name === 'login') return user.value ? '/reports' : true
  if (!user.value) return { name: 'login', query: { next: to.fullPath } }
  if (typeof to.meta.grant === 'string' && !hasGrant(to.meta.grant)) return { name: 'missing' }
})
export default router
