<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, errorText, params } from '../api'
import { hasGrant, user } from '../auth'
import QueryPreview from '../components/QueryResult.vue'
import { dateText, scopeText, type Page, type QueryDetail, type QueryLog, type Scope } from '../types'

const route = useRoute()
const contextId = computed(() => typeof route.query.context === 'string' ? route.query.context : undefined)
const data = ref<QueryLog[]>([])
const total = ref(0)
const current = ref(1)
const userId = ref<number>()
const start = ref('')
const end = ref('')
const error = ref('')
const busy = ref(false)
const dialog = ref(false)
const detail = ref<QueryDetail>()
const labels: Record<string, string> = { ok: '成功', denied: '越权', invalid: '参数错误', error: '执行错误' }
let seq = 0
async function load() {
  const request = ++seq
  busy.value = true
  error.value = ''
  try {
    const result = await api<Page<QueryLog>>('/queries' + params({ user_id: userId.value, context_id: contextId.value, start: start.value, end: end.value,
      limit: 15, offset: (current.value - 1) * 15 }))
    if (seq === request) { data.value = result.items; total.value = result.total }
  } catch (err) { if (seq === request) error.value = errorText(err) } finally { if (seq === request) busy.value = false }
}
function filter() { current.value = 1; void load() }
function reset() { userId.value = undefined; start.value = ''; end.value = ''; filter() }
async function open(id: number) {
  try { detail.value = await api('/queries/' + id); dialog.value = true }
  catch (err) { error.value = errorText(err) }
}
onMounted(load)
watch(contextId, filter)
</script>
<template>
  <div class="page-title"><h1>查询记录</h1><p>查看指标查询的执行时间、范围、返回行数和结果。</p></div>
  <div v-if="contextId" class="section-head"><RouterLink to="/contexts" class="text-link">返回分析上下文</RouterLink><RouterLink to="/queries" class="text-link">查看全部查询</RouterLink></div>
  <section class="panel">
    <div class="section-head"><h2>执行历史</h2><span class="muted">{{ total }} 条记录</span></div>
    <form class="toolbar" @submit.prevent="filter">
      <el-input-number v-model="userId" :min="1" :controls="false" placeholder="用户 ID" aria-label="用户 ID" />
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
      <el-table-column label="执行状态" width="105"><template #default="{ row }"><el-tag :type="row.status === 'ok' ? 'success' : 'danger'" effect="plain">{{ labels[row.status] ?? row.status }}</el-tag></template></el-table-column>
      <el-table-column label="结果行数" prop="row_count" width="100" />
      <el-table-column label="执行时间（UTC）" min-width="168"><template #default="{ row }">{{ dateText(row.created_at, 'UTC') }}</template></el-table-column>
      <el-table-column label="操作" width="82"><template #default="{ row }"><el-button text type="primary" @click="open(row.id)">详情</el-button></template></el-table-column>
    </el-table>
    <div class="pagination"><el-pagination v-model:current-page="current" :page-size="15" :total="total" background layout="prev, pager, next" @current-change="load" /></div>
  </section>
  <el-dialog v-model="dialog" :title="'查询记录 #' + detail?.id" width="min(720px, 94vw)">
    <QueryPreview v-if="detail?.result" :result="detail.result" :export-name="'query-' + detail.id" />
    <h3>查询参数</h3><pre class="json-box">{{ JSON.stringify(detail?.filters, null, 2) }}</pre>
    <template #footer>
      <RouterLink v-if="detail?.result && detail.user_id === user?.id && detail.scope !== 'all' && hasGrant('report.create')"
                  class="text-link" :to="{ name: 'create', query: { fromQuery: detail.id } }">用此结果新建报告</RouterLink>
    </template>
  </el-dialog>
</template>
