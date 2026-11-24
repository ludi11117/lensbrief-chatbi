<script setup lang="ts">
import { FileBarChart2, FileCheck2, FilePenLine, Plus, Archive, ArrowUpRight, SearchX } from '@lucide/vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorText, params } from '../api'
import { hasGrant } from '../auth'
import { dateText, type Page, type ReportRow, type ReportSummary, type Status } from '../types'
import ReportFilters from '../components/ReportFilters.vue'
import StatusPill from '../components/StatusPill.vue'
import { useEntrance } from '../useEntrance'

const entrance = ref<HTMLElement>()
useEntrance(entrance)

const router = useRouter()
const route = useRoute()
const pageSizes = [5, 10, 20, 50]
const states = [
  { key: '', label: '全部报告', icon: FileBarChart2 },
  { key: 'draft', label: '草稿', icon: FilePenLine },
  { key: 'published', label: '已发布', icon: FileCheck2 },
  { key: 'archived', label: '已归档', icon: Archive },
] as const
const rows = ref<ReportRow[]>([])
const totals = ref<ReportSummary>()
const status = ref<Status | ''>('')
const keyword = ref('')
const total = ref(0)
const current = ref(1)
const limit = ref(10)
const busy = ref(false)
const error = ref('')
let requestId = 0
async function load() {
  const id = ++requestId
  busy.value = true
  error.value = ''
  try {
    const result = await api<Page<ReportRow>>('/reports' + params({
      q: keyword.value.trim(), status: status.value, limit: limit.value, offset: (current.value - 1) * limit.value,
    }))
    if (id === requestId) {
      const lastPage = Math.max(1, Math.ceil(result.total / result.limit))
      if (current.value > lastPage) {
        current.value = lastPage
        updateUrl()
        return
      }
      rows.value = result.items
      total.value = result.total
    }
  } catch (err) { if (id === requestId) error.value = errorText(err) }
  finally { if (id === requestId) busy.value = false }
}
function loadFromUrl() {
  const query = route.query
  keyword.value = typeof query.q === 'string' ? query.q.slice(0, 120) : ''
  status.value = states.find(item => item.key === query.status)?.key ?? ''
  const rawSize = typeof query.size === 'string' ? Number(query.size) : 10
  limit.value = pageSizes.includes(rawSize) ? rawSize : 10
  const page = typeof query.page === 'string' ? Number(query.page) : 1
  current.value = page > 0 && Number.isSafeInteger(page) && Number.isSafeInteger(page * limit.value) ? page : 1
  void load()
}
function updateUrl() {
  const query = {
    q: keyword.value.trim() || undefined,
    status: status.value || undefined,
    page: current.value === 1 ? undefined : String(current.value),
    size: limit.value === 10 ? undefined : String(limit.value),
  }
  if (Object.entries(query).every(([key, value]) => route.query[key] === value)) {
    void load()
  } else void router.replace({ query })
}
function filter() { current.value = 1; updateUrl() }
function selectStatus(value: Status | '') { status.value = value; filter() }
function reset() { keyword.value = ''; selectStatus('') }
async function loadSummary() {
  try { totals.value = await api<ReportSummary>('/reports/summary') }
  catch { totals.value = undefined }
}
onMounted(() => {
  loadFromUrl()
  void loadSummary()
})
watch(() => route.query, () => { if (route.name === 'reports') loadFromUrl() })
</script>
<template>
  <div ref="entrance" class="reports-page">
  <section class="hero" data-enter>
    <div><span class="hero-kicker">运营分析</span><h1>报告中心</h1><p>从查询到发布，保留每一次分析的依据。</p></div>
    <div class="report-index" aria-hidden="true">R<span>↗</span></div>
    <el-button v-if="hasGrant('report.create')" type="primary" size="large" @click="router.push('/reports/new')"><Plus :size="18" /> 新建报告</el-button>
  </section>
  <div class="stat-grid" data-enter aria-label="按报告状态筛选">
    <button v-for="(item, index) in states" :key="item.key" type="button" class="stat" :class="{ selected: status === item.key }"
            :aria-pressed="status === item.key" @click="selectStatus(item.key)">
      <span class="stat-icon" :class="'tone-' + index"><component :is="item.icon" :size="20" /></span>
      <span><small>{{ item.label }}</small><strong>{{ totals?.[item.key || 'total'] ?? '—' }}</strong></span>
    </button>
  </div>
  <section class="panel report-list" data-enter>
    <div class="section-head"><div><h2>报告列表</h2><p>查看工作稿，或继续一份尚未完成的分析。</p></div><span class="list-count" aria-live="polite">{{ busy ? '加载中' : `${total} 条报告` }}</span></div>
    <ReportFilters v-model:keyword="keyword" :status="status" @update:status="selectStatus($event as Status | '')" @search="filter" @reset="reset" />
    <el-alert v-if="error" type="error" :title="error" :closable="false"><el-button text @click="load">重试</el-button></el-alert>
    <el-table v-loading="busy" :data="rows" empty-text="暂无符合条件的报告" class="report-table desktop-report-table">
      <el-table-column label="报告名称" min-width="260">
        <template #default="{ row }"><RouterLink class="report-link" :to="'/reports/' + row.id">
          <span class="row-icon"><FileBarChart2 :size="19" /></span><span><strong>{{ row.title }}</strong><small>{{ row.description || '—' }}</small></span>
        </RouterLink></template>
      </el-table-column>
      <el-table-column label="状态" width="120"><template #default="{ row }"><StatusPill :status="row.status" /></template></el-table-column>
      <el-table-column label="当前版本" width="105"><template #default="{ row }">{{ row.current_version ? 'v' + row.current_version : '—' }}</template></el-table-column>
      <el-table-column label="归属人" prop="owner_name" width="105" />
      <el-table-column label="更新时间" min-width="175"><template #default="{ row }">{{ dateText(row.updated_at) }}</template></el-table-column>
      <el-table-column label="操作" width="90"><template #default="{ row }"><RouterLink class="text-link" :to="'/reports/' + row.id">查看</RouterLink></template></el-table-column>
    </el-table>
    <div class="mobile-report-list" :aria-busy="busy">
      <RouterLink v-for="row in rows" :key="row.id" :to="'/reports/' + row.id" class="mobile-report-card">
        <div class="split"><StatusPill :status="row.status" /><ArrowUpRight :size="18" /></div>
        <h3>{{ row.title }}</h3><p>{{ row.description || '暂无描述' }}</p>
        <div class="mobile-report-meta"><span>{{ row.owner_name }} · {{ row.current_version ? 'v' + row.current_version : '未发布' }}</span><time>{{ dateText(row.updated_at) }}</time></div>
      </RouterLink>
      <div v-if="!busy && !rows.length && !error" class="report-empty"><SearchX :size="30" /><h3>暂无符合条件的报告</h3><p>试试其他关键词或报告状态。</p><el-button @click="reset">重置筛选</el-button></div>
    </div>
    <div v-if="total" class="pagination"><el-pagination v-model:current-page="current" v-model:page-size="limit" :page-sizes="pageSizes" :total="total" background
        layout="prev, pager, next, sizes" @current-change="updateUrl" @size-change="filter" /></div>
  </section>
  <p class="workspace-note">演示销售数据 · 报告可见范围由你的角色与部门决定</p>
  </div>
</template>
