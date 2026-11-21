<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { BookOpen, Plus, X } from 'lucide-vue-next'
import { onMounted, reactive, ref, watch } from 'vue'
import { api, errorText, params } from '../api'
import { hasGrant } from '../auth'
import { type CatalogMetric, type Dataset, type KnowledgeItem, type KnowledgePack, type KnowledgePackRow, type Page } from '../types'

const rows = ref<KnowledgePackRow[]>([])
const datasets = ref<Dataset[]>([])
const metrics = ref<CatalogMetric[]>([])
const current = ref(1)
const total = ref(0)
const datasetFilter = ref<number>()
const loading = ref(false)
const saving = ref(false)
const detailsOpen = ref(false)
const editorOpen = ref(false)
const details = ref<KnowledgePack>()
const error = ref('')
const formError = ref('')
const editingId = ref<number>()
const form = reactive({ dataset_id: 0, title: '', description: '', items: [] as KnowledgeItem[] })
const blank = () => ({ title: '', content: '', metric_id: null })
let metricRequest = 0

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await api<Page<KnowledgePackRow>>('/knowledge/packs' + params({
      dataset_id: datasetFilter.value, limit: 10, offset: (current.value - 1) * 10,
    }))
    rows.value = response.items
    total.value = response.total
  } catch (err) { error.value = errorText(err) } finally { loading.value = false }
}
onMounted(async () => {
  await load()
  try { datasets.value = (await api<Page<Dataset>>('/datasets?limit=100')).items }
  catch (err) { error.value = errorText(err) }
})
watch(() => form.dataset_id, async id => {
  const requestId = ++metricRequest
  metrics.value = []
  if (!id) return
  try {
    const response = await api<Page<CatalogMetric>>('/datasets/' + id + '/metrics?limit=100')
    if (requestId === metricRequest) metrics.value = response.items
  } catch (err) { if (requestId === metricRequest) formError.value = errorText(err) }
})
async function inspect(id: number) {
  try {
    details.value = await api<KnowledgePack>('/knowledge/packs/' + id)
    detailsOpen.value = true
  } catch (err) { error.value = errorText(err) }
}
function edit(pack?: KnowledgePack) {
  editingId.value = pack?.id
  formError.value = ''
  Object.assign(form, { dataset_id: pack?.dataset_id ?? datasets.value[0]?.id ?? 0, title: pack?.title ?? '',
    description: pack?.description ?? '', items: pack?.items.map(item => ({ ...item })) ?? [blank()] })
  detailsOpen.value = false
  editorOpen.value = true
}
function datasetChanged() { for (const item of form.items) item.metric_id = null }
function changeFilter() { current.value = 1; void load() }
async function save() {
  if (!form.dataset_id || !form.title.trim() || form.items.some(item => !item.title.trim() || !item.content.trim())) {
    formError.value = '请填写知识包名称、条目标题和内容，并选择数据集。'
    return
  }
  saving.value = true
  formError.value = ''
  try {
    await api(editingId.value ? '/knowledge/packs/' + editingId.value : '/knowledge/packs', {
      method: editingId.value ? 'PUT' : 'POST', body: JSON.stringify(form),
    })
    editorOpen.value = false
    ElMessage.success('知识包已保存')
    await load()
  } catch (err) { formError.value = errorText(err) } finally { saving.value = false }
}
const datasetName = (id: number) => datasets.value.find(item => item.id === id)?.name ?? '数据集 #' + id
</script>

<template>
  <div class="page-title split">
    <div><h1>场景知识包</h1><p>查看复盘场景的指标口径，在分析上下文中选用。</p></div>
    <el-button v-if="hasGrant('knowledge.manage')" type="primary" :disabled="!datasets.length" @click="edit()"><Plus :size="18" /> 新建知识包</el-button>
  </div>
  <el-alert v-if="error" class="page-alert" :title="error" type="error" :closable="false" />
  <section v-loading="loading" class="panel">
    <div class="section-head">
      <h2>知识目录</h2>
      <el-select v-model="datasetFilter" aria-label="筛选数据集" clearable placeholder="全部数据集" class="select-compact" @change="changeFilter">
        <el-option v-for="data in datasets" :key="data.id" :value="data.id" :label="data.name" />
      </el-select>
    </div>
    <el-empty v-if="!rows.length" description="暂无知识包" :image-size="70" />
    <div v-else class="knowledge-grid">
      <button v-for="pack in rows" :key="pack.id" type="button" class="knowledge-card" @click="inspect(pack.id)">
        <span class="card-top"><span class="row-icon"><BookOpen :size="18" /></span><span class="version-label">v{{ pack.revision }}</span></span>
        <strong>{{ pack.title }}</strong><span class="muted">{{ pack.description }}</span><small>{{ datasetName(pack.dataset_id) }}</small>
      </button>
    </div>
    <div v-if="total > 10" class="pagination"><el-pagination v-model:current-page="current" :page-size="10" :total="total" background layout="prev, pager, next" @current-change="load" /></div>
  </section>
  <el-dialog v-model="detailsOpen" :title="details?.title" width="min(610px, 92vw)">
    <template v-if="details">
      <div class="inline"><span class="version-label">v{{ details.revision }}</span><span class="muted">{{ datasetName(details.dataset_id) }}</span></div>
      <p class="preview-description">{{ details.description }}</p>
      <article v-for="(item, index) in details.items" :key="index" class="knowledge-item">
        <h3>{{ item.title }}</h3><p>{{ item.content }}</p>
      </article>
    </template>
    <template #footer><el-button v-if="details && hasGrant('knowledge.manage')" type="primary" @click="edit(details)">编辑知识包</el-button></template>
  </el-dialog>
  <el-dialog v-model="editorOpen" :title="editingId ? '编辑知识包' : '新建知识包'" width="min(620px, 92vw)">
    <form class="form-panel" @submit.prevent="save">
      <el-alert v-if="formError" :title="formError" type="error" :closable="false" />
      <label for="pack-title">名称</label><el-input id="pack-title" v-model="form.title" maxlength="120" />
      <label>数据集</label>
      <el-select v-model="form.dataset_id" aria-label="数据集" :disabled="editingId !== undefined" @change="datasetChanged">
        <el-option v-for="data in datasets" :key="data.id" :value="data.id" :label="data.name" />
      </el-select>
      <label for="pack-description">适用场景</label><el-input id="pack-description" v-model="form.description" maxlength="500" />
      <section v-for="(item, index) in form.items" :key="index" class="knowledge-item form-panel">
        <div class="section-head"><h3>知识条目</h3><button type="button" class="icon-button" aria-label="删除该条目" :disabled="form.items.length <= 1" @click="form.items.splice(index, 1)"><X :size="14" /></button></div>
        <el-input v-model="item.title" aria-label="条目标题" placeholder="口径或检查项" maxlength="120" />
        <el-input v-model="item.content" aria-label="条目内容" type="textarea" :rows="2" maxlength="800" />
        <el-select :model-value="item.metric_id ?? undefined" aria-label="适用指标" clearable placeholder="所有指标"
                   @update:model-value="(value: number | undefined) => item.metric_id = value || null">
          <el-option v-for="metric in metrics" :key="metric.id" :value="metric.id" :label="metric.name" />
        </el-select>
      </section>
      <el-button :disabled="form.items.length >= 8" @click="form.items.push(blank())">添加条目</el-button>
      <div class="footer-actions"><el-button @click="editorOpen = false">取消</el-button><el-button native-type="submit" type="primary" :loading="saving">保存知识包</el-button></div>
    </form>
  </el-dialog>
</template>
