<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorText, params } from '../api'
import { hasGrant, user } from '../auth'
import QueryPreview from '../components/QueryResult.vue'
import { dateText, scopeText, type Page, type QueryDetail, type QueryLog, type QueryStatus, type Scope } from '../types'

const route = useRoute()
const router = useRouter()
const contextId = computed(() => typeof route.query.context === 'string' ? route.query.context : undefined)
const detailId = computed(() => {
  const id = typeof route.query.id === 'string' ? Number(route.query.id) : 0
  return Number.isSafeInteger(id) && id > 0 ? id : null
})
const dialog = computed({
  get: () => detailId.value !== null,
  set: (open: boolean) => { if (!open) selectDetail(null) },
})
const data = ref<QueryLog[]>([])
const total = ref(0)
const current = ref(1)
const userId = ref<number>()
const status = ref<QueryStatus>()
const start = ref('')
const end = ref('')
const error = ref('')
const busy = ref(false)
const detail = ref<QueryDetail>()
const detailError = ref('')
const labels: Record<QueryStatus, string> = { ok: '成功', denied: '越权', invalid: '参数错误', error: '执行错误' }
let seq = 0
async function load() {
  const request = ++seq
  busy.value = true
  error.value = ''
  try {
    const result = await api<Page<QueryLog>>('/queries' + params({ user_id: userId.value, context_id: contextId.value, start: start.value, end: end.value,
      status: status.value, limit: 15, offset: (current.value - 1) * 15 }))
    if (seq === request) { data.value = result.items; total.value = result.total }
  } catch (err) { if (seq === request) error.value = errorText(err) } finally { if (seq === request) busy.value = false }
}
function filter() { current.value = 1; void load() }
function reset() { userId.value = undefined; status.value = undefined; start.value = ''; end.value = ''; filter() }
function selectDetail(id: number | null) {
  void router.replace({ query: { ...route.query, id: id?.toString() } })
}
onMounted(load)
watch(contextId, filter)
watch(detailId, async (id, _previous, onCleanup) => {
  detail.value = undefined
  detailError.value = ''
  if (id === null) return
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  try {
    detail.value = await api<QueryDetail>('/queries/' + id, { signal: controller.signal })
  } catch (err) {
    if (!controller.signal.aborted) detailError.value = errorText(err)
  }
}, { immediate: true })
</script>
<template>
  <div class="page-title"><h1>查询记录</h1><p>查看指标查询的执行时间、范围、返回行数和结果。</p></div>
  <div v-if="contextId" class="section-head"><RouterLink to="/contexts" class="text-link">返回分析上下文</RouterLink><RouterLink to="/queries" class="text-link">查看全部查询</RouterLink></div>
  <section class="panel">
    <div class="section-head"><h2>执行历史</h2><span class="muted">{{ total }} 条记录</span></div>
    <form class="toolbar" @submit.prevent="filter">
      <el-input-number v-model="userId" :min="1" :controls="false" placeholder="用户 ID" aria-label="用户 ID" />
      <el-select v-model="status" class="status-select" placeholder="执行状态" aria-label="执行状态" clearable>
        <el-option v-for="(label, value) in labels" :key="value" :label="label" :value="value" />
      </el-select>
      <label class="date-filter">从 <input v-model="start" type="date" aria-label="查询开始日期（UTC）" class="date-input" /></label>
      <label class="date-filter">至 <input v-model="end" type="date" aria-label="查询结束日期（UTC）" class="date-input" /></label>
      <el-button native-type="submit">筛选</el-button><el-button text @click="reset">重置</el-button>
    </form>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <el-table v-loading="busy" :data="data" empty-text="暂无查询记录">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户" width="112" />
      <el-table-column prop="dataset_name" label="数据集" min-width="125" />
      <el-table-column prop="metric" label="指标" min-width="105" />
      <el-table-column label="范围" width="75"><template #default="{ row }">{{ scopeText[row.scope as Scope] }}</template></el-table-column>
      <el-table-column label="执行状态" width="105"><template #default="{ row }"><el-tag :type="row.status === 'ok' ? 'success' : 'danger'" effect="plain">{{ labels[row.status as QueryStatus] }}</el-tag></template></el-table-column>
      <el-table-column label="结果行数" prop="row_count" width="100" />
      <el-table-column label="执行时间（UTC）" min-width="168"><template #default="{ row }">{{ dateText(row.created_at, 'UTC') }}</template></el-table-column>
      <el-table-column label="操作" width="82"><template #default="{ row }"><el-button text type="primary" @click="selectDetail(row.id)">详情</el-button></template></el-table-column>
    </el-table>
    <div class="pagination"><el-pagination v-model:current-page="current" :page-size="15" :total="total" background layout="prev, pager, next" @current-change="load" /></div>
  </section>
  <el-dialog v-model="dialog" :title="detailId ? '查询记录 #' + detailId : '查询记录'" width="min(720px, 94vw)">
    <el-alert v-if="detailError" type="error" :title="detailError" :closable="false" show-icon />
    <template v-else-if="detail">
      <div class="inline muted query-detail-meta">
        <el-tag :type="detail.status === 'ok' ? 'success' : 'danger'" effect="plain">{{ labels[detail.status] }}</el-tag>
        <time :datetime="detail.created_at">{{ dateText(detail.created_at, 'UTC') }} UTC</time>
        <span>耗时 {{ detail.elapsed_ms }} ms</span>
        <span>返回 {{ detail.row_count }} 行</span>
      </div>
      <QueryPreview v-if="detail.result" :result="detail.result" :export-name="'query-' + detail.id" />
      <details class="query-parameters">
        <summary>查询参数</summary>
        <pre class="json-box">{{ JSON.stringify(detail.filters, null, 2) }}</pre>
      </details>
    </template>
    <p v-else class="muted" role="status">正在加载查询详情…</p>
    <template #footer>
      <RouterLink v-if="detail?.result && detail.user_id === user?.id && detail.scope !== 'all' && hasGrant('report.create')"
                  class="text-link" :to="{ name: 'create', query: { fromQuery: detail.id } }">用此结果新建报告</RouterLink>
    </template>
  </el-dialog>
</template>
<style scoped>
.query-detail-meta { margin-bottom: 16px; flex-wrap: wrap }
.query-parameters { margin-top: 16px }
.query-parameters summary { cursor: pointer }
</style>
