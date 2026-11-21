<script setup lang="ts">
import { FileBarChart2, FileCheck2, FilePenLine, Plus, Archive } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, params } from '../api'
import { hasGrant } from '../auth'
import { dateText, type Page, type ReportRow, type ReportSummary, type Status } from '../types'
import ReportFilters from '../components/ReportFilters.vue'
import StatusPill from '../components/StatusPill.vue'

const router = useRouter()
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
      rows.value = result.items
      total.value = result.total
    }
  } catch (err) { if (id === requestId) error.value = errorText(err) }
  finally { if (id === requestId) busy.value = false }
}
function filter() { current.value = 1; void load() }
function selectStatus(value: Status | '') { status.value = value; filter() }
function reset() { keyword.value = ''; selectStatus('') }
async function loadSummary() {
  try { totals.value = await api<ReportSummary>('/reports/summary') }
  catch { totals.value = undefined }
}
onMounted(() => {
  void load()
  void loadSummary()
})
</script>
<template>
  <section class="hero">
    <div><span class="hero-kicker">运营分析</span><h1>报告中心</h1><p>管理销售报告、附件和发布记录。</p></div>
    <el-button v-if="hasGrant('report.create')" type="primary" size="large" @click="router.push('/reports/new')"><Plus :size="18" /> 新建报告</el-button>
  </section>
  <div class="stat-grid">
    <button v-for="(item, index) in states" :key="item.key" type="button" class="stat" :class="{ selected: status === item.key }"
            :aria-pressed="status === item.key" @click="selectStatus(item.key)">
      <span class="stat-icon" :class="'tone-' + index"><component :is="item.icon" :size="20" /></span>
      <span><small>{{ item.label }}</small><strong>{{ totals?.[item.key || 'total'] ?? '—' }}</strong></span>
    </button>
  </div>
  <section class="panel report-list">
    <div class="section-head"><h2>报告列表</h2><span class="muted">{{ total }} 条报告</span></div>
    <ReportFilters v-model:keyword="keyword" :status="status" @update:status="selectStatus($event as Status | '')" @search="filter" @reset="reset" />
    <el-alert v-if="error" type="error" :title="error" :closable="false"><el-button text @click="load">重试</el-button></el-alert>
    <el-table v-loading="busy" :data="rows" empty-text="暂无符合条件的报告" class="report-table">
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
    <div class="pagination"><el-pagination v-model:current-page="current" v-model:page-size="limit" :page-sizes="[5, 10, 20, 50]" :total="total" background
        layout="prev, pager, next, sizes" @current-change="load" @size-change="filter" /></div>
  </section>
</template>
