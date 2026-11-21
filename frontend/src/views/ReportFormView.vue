<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { FileUp, Play, Sparkles, X } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorText, params } from '../api'
import { hasGrant, user } from '../auth'
import QueryPreview from '../components/QueryResult.vue'
import { type AnalysisContext, type Asset, type Dataset, type Page, type QueryResult, type Report, type Scope } from '../types'

interface CatalogEntry { code: string; name: string; description: string }
const route = useRoute()
const router = useRouter()
const reportId = computed(() => route.params.id ? Number(route.params.id) : null)
const form = reactive({ title: '', description: '', content: '', dataset_id: null as number | null })
const goal = ref('')
const media = ref<Asset[]>([])
const result = ref<QueryResult | null>(null)
const queryId = ref<number | null>(null)
const datasets = ref<Dataset[]>([])
const contexts = ref<AnalysisContext[]>([])
const contextId = ref<number | null>(null)
const selectedContext = computed(() => contexts.value.find(item => item.id === contextId.value))
const metricList = ref<CatalogEntry[]>([])
const dimensionList = ref<CatalogEntry[]>([])
const fields = reactive({ metric: 'gmv', dimension: 'channel', start: '2026-10-01', end: '2026-10-31' })
const waiting = ref(false)
const saving = ref(false)
const querying = ref(false)
const generating = ref(false)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()
const error = ref('')
const blocked = ref(false)
let catalogRequest = 0

async function refreshCatalog(id: number | null) {
  const seq = ++catalogRequest
  metricList.value = []
  dimensionList.value = []
  contexts.value = []
  if (!id) return
  try {
    const [metrics, dimensions, saved] = await Promise.all([
      api<Page<CatalogEntry>>('/datasets/' + id + '/metrics'),
      api<Page<CatalogEntry>>('/datasets/' + id + '/dimensions'),
      hasGrant('dataset.query') ? api<Page<AnalysisContext>>('/contexts' + params({ dataset_id: id, archived: 'false', limit: 100 })) : null,
    ])
    if (catalogRequest !== seq) return
    metricList.value = metrics.items
    dimensionList.value = dimensions.items
    contexts.value = saved?.items ?? []
    if (!metrics.items.some(item => item.code === fields.metric)) fields.metric = metrics.items[0]?.code ?? ''
    if (!dimensions.items.some(item => item.code === fields.dimension)) fields.dimension = dimensions.items[0]?.code ?? ''
  } catch (err) { if (catalogRequest === seq) error.value = errorText(err) }
}
watch(() => form.dataset_id, refreshCatalog)

onMounted(async () => {
  waiting.value = true
  try {
    if (reportId.value) {
      const report = await api<Report>('/reports/' + reportId.value)
      if (!report.allowed.edit || report.status === 'archived') { blocked.value = true; return }
      Object.assign(form, { title: report.title, description: report.description, content: report.content,
        dataset_id: report.dataset_id })
      media.value = report.assets
      result.value = report.query
      queryId.value = report.query_id
      if (report.query) { fields.start = report.query.start; fields.end = report.query.end }
    }
    if (hasGrant('dataset.read')) {
      datasets.value = (await api<Page<Dataset>>('/datasets')).items
      if (!reportId.value) {
        const fromContext = typeof route.query.context === 'string' && Number(route.query.context)
        if (fromContext) {
          const saved = await api<AnalysisContext>('/contexts/' + fromContext)
          if (saved.archived) { error.value = '请先恢复已归档的分析上下文。'; blocked.value = true; return }
          form.dataset_id = saved.dataset_id
          contextId.value = saved.id
          goal.value = saved.objective
        } else form.dataset_id = datasets.value[0]?.id ?? null
      }
    }
  } catch (err) { error.value = errorText(err); blocked.value = true } finally { waiting.value = false }
})

function changeDataset(value: number | null) {
  form.dataset_id = value ?? null
  changeContext(null)
}
function changeContext(value: number | null) {
  const previous = selectedContext.value?.objective
  contextId.value = value || null
  if (!goal.value || goal.value === previous) goal.value = selectedContext.value?.objective ?? ''
  result.value = null
  queryId.value = null
}
async function runQuery() {
  querying.value = true
  error.value = ''
  try {
    const grant = user.value?.grants['dataset.query']
    const scope: Scope = grant === 'own' ? 'own' : 'department'
    const response = await api<QueryResult & { id: number }>('/queries', {
      method: 'POST', body: JSON.stringify({ dataset_id: form.dataset_id, ...fields, scope, context_id: contextId.value }),
    })
    if (reportId.value && result.value && queryId.value) {
      ElMessage.info('本次查询将替换工作稿关联的数据。')
    }
    result.value = response
    queryId.value = response.id
  } catch (err) { error.value = errorText(err) } finally { querying.value = false }
}
async function generateDraft() {
  if (form.content && !window.confirm('用生成的草稿覆盖当前标题、摘要和正文？')) return
  generating.value = true
  error.value = ''
  try {
    const draft = await api<{title: string; description: string; content: string; mode: string}>('/drafts/generate', {
      method: 'POST', body: JSON.stringify({ query_id: queryId.value, goal: goal.value }),
    })
    form.title = draft.title
    form.description = draft.description
    form.content = draft.content
    ElMessage.success(draft.mode === 'mock' ? '已生成离线草稿' : '已生成模型草稿')
  } catch (err) { error.value = errorText(err) } finally { generating.value = false }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const body = new FormData()
  body.append('file', file)
  uploading.value = true
  error.value = ''
  try { media.value = [...media.value, await api<Asset>('/assets', { method: 'POST', body })] }
  catch (err) { error.value = errorText(err) } finally { uploading.value = false; input.value = '' }
}
async function save() {
  if (!form.title.trim()) { error.value = '请输入报告标题。'; return }
  saving.value = true
  error.value = ''
  try {
    const report = await api<Report>(reportId.value ? '/reports/' + reportId.value : '/reports', {
      method: reportId.value ? 'PUT' : 'POST',
      body: JSON.stringify({ ...form, query_id: queryId.value, asset_ids: media.value.map(file => file.id) }),
    })
    ElMessage.success('工作稿已保存')
    await router.push('/reports/' + report.id)
  } catch (err) { error.value = errorText(err) } finally { saving.value = false }
}
</script>

<template>
  <RouterLink class="text-link" :to="reportId ? '/reports/' + reportId : '/reports'">返回{{ reportId ? '详情' : '报告中心' }}</RouterLink>
  <div class="page-title"><h1>{{ reportId ? '编辑报告' : '新建报告' }}</h1><p>整理业务发现并保存工作稿，发布后生成版本记录。</p></div>
  <el-alert v-if="error || blocked" :title="error || '当前报告不可编辑。'" type="error" show-icon :closable="false" class="page-alert" />
  <div v-if="!blocked" v-loading="waiting" class="editor-grid">
    <form class="panel form-panel" @submit.prevent="save">
      <h2>报告内容</h2>
      <label for="title">报告标题</label><el-input id="title" v-model="form.title" maxlength="120" show-word-limit placeholder="例如：十月渠道表现复盘" />
      <label for="description">摘要</label><el-input id="description" v-model="form.description" maxlength="500" placeholder="概述这份报告关注的问题" />
      <label for="body">正文</label><el-input id="body" v-model="form.content" type="textarea" :rows="12" maxlength="16000" show-word-limit placeholder="写入主要发现和统计口径" />
      <div class="section-head attachments-heading"><h3>附件</h3><el-button v-if="hasGrant('asset.upload')" :disabled="media.length >= 12" :loading="uploading" @click="fileInput?.click()"><FileUp :size="16" /> 上传文件</el-button></div>
      <input ref="fileInput" type="file" class="hidden-input" aria-label="上传附件" accept=".png,.jpg,.jpeg,.pdf,.csv" @change="upload" />
      <p v-if="!media.length" class="muted">支持 PNG、JPEG、PDF 和 CSV，单文件上限 5 MiB。</p>
      <div v-for="file in media" :key="file.id" class="attachment"><span>{{ file.filename }}</span><button type="button" class="icon-button" :aria-label="'移除 ' + file.filename" @click="media = media.filter(item => item.id !== file.id)"><X :size="16" /></button></div>
      <div class="footer-actions"><el-button :disabled="saving" @click="router.back()">取消</el-button><el-button type="primary" native-type="submit" :loading="saving" :disabled="waiting || uploading || generating">保存报告</el-button></div>
    </form>
    <section class="panel form-panel">
      <h2>关联数据</h2>
      <template v-if="hasGrant('dataset.read')">
        <label>数据集</label><el-select aria-label="数据集" :model-value="form.dataset_id ?? undefined" clearable placeholder="选择数据集" @change="changeDataset">
          <el-option v-for="item in datasets" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <template v-if="form.dataset_id && hasGrant('dataset.query')">
          <template v-if="contexts.length">
            <label>分析上下文</label>
            <el-select :model-value="contextId ?? undefined" aria-label="分析上下文" clearable placeholder="选填"
                       :disabled="querying || generating" @update:model-value="changeContext">
              <el-option v-for="item in contexts" :key="item.id" :value="item.id" :label="item.title" />
            </el-select>
            <p v-if="selectedContext?.pack_title" class="muted">使用知识包 · {{ selectedContext.pack_title }}</p>
          </template>
          <div class="field-grid"><div><label>指标</label><el-select v-model="fields.metric" aria-label="指标"><el-option v-for="item in metricList" :key="item.code" :value="item.code" :label="item.name" /></el-select></div>
            <div><label>维度</label><el-select v-model="fields.dimension" aria-label="维度"><el-option v-for="item in dimensionList" :key="item.code" :value="item.code" :label="item.name" /></el-select></div></div>
          <div class="field-grid"><div><label for="start-day">开始日期</label><input id="start-day" v-model="fields.start" type="date" class="date-input" /></div>
            <div><label for="end-day">结束日期</label><input id="end-day" v-model="fields.end" type="date" class="date-input" /></div></div>
          <el-button :loading="querying" :disabled="!fields.start || !fields.end || !metricList.length" @click="runQuery"><Play :size="15" /> 运行指标查询</el-button>
        </template>
      </template>
      <template v-if="result">
        <QueryPreview :result="result" />
        <template v-if="hasGrant('report.create')">
          <label for="goal">分析目标（可选）</label><el-input id="goal" v-model="goal" maxlength="500" placeholder="希望报告回答什么？" />
          <el-button plain type="primary" :loading="generating" :disabled="querying" @click="generateDraft"><Sparkles :size="16" /> 生成报告草稿</el-button>
        </template>
      </template>
    </section>
  </div>
</template>
