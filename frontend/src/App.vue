<script setup lang="ts">
import BrandMark from './components/BrandMark.vue'
import { Activity, BookOpen, ChevronDown, Database, FileBarChart2, Folders, ShieldCheck } from '@lucide/vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { hasGrant, signOut, user } from './auth'

const route = useRoute()
const router = useRouter()
const links = [
  { path: '/reports', label: '报告中心', icon: FileBarChart2, grant: 'report.read' },
  { path: '/contexts', label: '分析上下文', icon: Folders, grant: 'dataset.query' },
  { path: '/knowledge', label: '场景知识包', icon: BookOpen, grant: 'dataset.read' },
  { path: '/queries', label: '查询记录', icon: Database, grant: 'query.read' },
  { path: '/access', label: '权限管理', icon: ShieldCheck, grant: 'user.manage' },
]
function logout() {
  signOut()
  void router.push('/login')
}
</script>

<template>
  <el-config-provider :locale="zhCn">
  <RouterView v-if="route.name === 'login'" />
  <div v-else class="shell">
    <a class="skip-link" href="#workspace-content">跳到主要内容</a>
    <aside class="sidebar">
      <RouterLink to="/reports" class="brand">
        <BrandMark />
        <span><strong>LensBrief</strong><small>数据运营工作台</small></span>
      </RouterLink>
      <nav aria-label="工作台导航">
        <div class="nav-heading">工作台</div>
        <template v-for="item in links" :key="item.path">
          <RouterLink v-if="hasGrant(item.grant)" :to="item.path" :class="{ active: route.path.startsWith(item.path) }">
            <component :is="item.icon" :size="18" /><span>{{ item.label }}</span>
          </RouterLink>
        </template>
      </nav>
      <div class="sidebar-foot"><Activity :size="15" /><span>运动相机销售数据集<small>演示环境 / 2026.10</small></span></div>
    </aside>
    <div class="workspace">
      <header class="topbar">
        <div class="bread"><span>LensBrief</span><span>/</span><strong>{{ route.meta.label }}</strong></div>
        <el-dropdown v-if="user" @command="logout">
          <button class="account" type="button"><span class="avatar">{{ user.name[0] }}</span>{{ user.name }}<ChevronDown :size="15" /></button>
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="logout">退出登录</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
      </header>
      <main id="workspace-content" class="content" tabindex="-1"><RouterView :key="route.path" /></main>
    </div>
  </div>
  </el-config-provider>
</template>
