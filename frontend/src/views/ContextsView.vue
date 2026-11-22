<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { Plus } from '@lucide/vue'
import { onMounted, reactive, ref, watch } from 'vue'
import { api, errorText, params } from '../api'
import { hasGrant } from '../auth'
import { dateText, type AnalysisContext, type AnalysisContextInput, type Dataset, type KnowledgePackRow, type Page } from '../types'

const rows = ref<AnalysisContext[]>([])
const datasets = ref<Dataset[]>([])
const packs = ref<KnowledgePackRow[]>([])
const current = ref(1)
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const open = ref(false)
const error = ref('')
const formError = ref('')
const selectedId = ref<number | null>(null)
const form = reactive<AnalysisContextInput>({ dataset_id: 0, knowledge_pack_id: null, title: '', objective: '', archived: false })
let packRequest = 0

async function load() {
  loading.value = true
  error.value = ''
  try {
    const result = await api<Page<AnalysisContext>>('/contexts' + params({ limit: 10, offset: (current.value - 1) * 10 }))
    rows.value = result.items
    total.value = result.total
  } catch (err) { error.value = errorText(err) } finally { loading.value = false }
}
onMounted(async () => {
  await load()
  try { datasets.value = (await api<Page<Dataset>>('/datasets?limit=100')).items }
  catch (err) { error.value = errorText(err) }
})
watch(() => form.dataset_id, async id => {
  const requestId = ++packRequest
  packs.value = []
  if (!id) return
  try {
    const response = await api<Page<KnowledgePackRow>>('/knowledge/packs' + params({ dataset_id: id, limit: 100 }))
    if (requestId === packRequest) packs.value = response.items
  } catch (err) { if (requestId === packRequest) formError.value = errorText(err) }
})
function edit(row?: AnalysisContext) {
  selectedId.value = row?.id ?? null
  formError.value = ''
  Object.assign(form, { dataset_id: row?.dataset_id ?? datasets.value[0]?.id ?? 0,
    knowledge_pack_id: row?.knowledge_pack_id ?? null, title: row?.title ?? '',
    objective: row?.objective ?? '', archived: row?.archived ?? false })
  open.value = true
}
function datasetChanged() { form.knowledge_pack_id = null }
async function save() {
  if (!form.dataset_id || !form.title.trim()) { formError.value = '请填写名称并选择数据集。'; return }
  saving.value = true
  formError.value = ''
  try {
    await api(selectedId.value ? '/contexts/' + selectedId.value : '/contexts', {
      method: selectedId.value ? 'PUT' : 'POST',
      body: JSON.stringify(form),
    })
    open.value = false
    ElMessage.success('上下文已保存')
    await load()
  } catch (err) { formError.value = errorText(err) } finally { saving.value = false }
}
const datasetName = (id: number) => datasets.value.find(item => item.id === id)?.name ?? '数据集 #' + id
</script>

<template>
  <div class="page-title split">
    <div><h1>分析上下文</h1><p>为同一个分析目标保存数据集、知识包和查询记录。</p></div>
    <el-button type="primary" :disabled="!datasets.length" @click="edit()"><Plus :size="18" /> 新建上下文</el-button>
  </div>
  <el-alert v-if="error" class="page-alert" :title="error" type="error" :closable="false" />
  <section class="panel">
    <div class="section-head"><h2>我的上下文</h2><span class="muted">{{ total }} 条</span></div>
    <el-table v-loading="loading" :data="rows" empty-text="暂无上下文">
      <el-table-column prop="title" label="名称" min-width="160" />
      <el-table-column prop="objective" label="分析目标" show-overflow-tooltip min-width="140" />
      <el-table-column label="数据集" min-width="120"><template #default="{ row }">{{ datasetName(row.dataset_id) }}</template></el-table-column>
      <el-table-column label="知识包" prop="pack_title" min-width="120" />
      <el-table-column label="状态" width="84"><template #default="{ row }"><el-tag :type="row.archived ? 'info' : 'success'" effect="plain">{{ row.archived ? '已归档' : '进行中' }}</el-tag></template></el-table-column>
      <el-table-column label="更新于" min-width="160"><template #default="{ row }">{{ dateText(row.updated_at) }}</template></el-table-column>
      <el-table-column label="操作" min-width="200"><template #default="{ row }">
        <div class="table-links">
          <RouterLink class="text-link" :to="{ name: 'queries', query: { context: row.id } }">查询历史</RouterLink>
          <RouterLink v-if="!row.archived && hasGrant('report.create')" class="text-link" :to="{ name: 'create', query: { context: row.id } }">新建报告</RouterLink>
          <el-button type="primary" text @click="edit(row)">编辑</el-button>
        </div>
      </template></el-table-column>
    </el-table>
    <div v-if="total > 10" class="pagination"><el-pagination v-model:current-page="current" :page-size="10" :total="total" background layout="prev, pager, next" @current-change="load" /></div>
  </section>
  <el-dialog v-model="open" :title="selectedId ? '编辑上下文' : '新建上下文'" width="min(525px, 92vw)">
    <form class="form-panel" @submit.prevent="save">
      <el-alert v-if="formError" :title="formError" type="error" :closable="false" />
      <label for="context-title">上下文名称</label>
      <el-input id="context-title" v-model="form.title" maxlength="120" />
      <label>数据集</label>
      <el-select v-model="form.dataset_id" aria-label="数据集" :disabled="selectedId !== null" @change="datasetChanged">
        <el-option v-for="data in datasets" :key="data.id" :value="data.id" :label="data.name" />
      </el-select>
      <label>场景知识包</label>
      <el-select :model-value="form.knowledge_pack_id ?? undefined" aria-label="场景知识包" clearable placeholder="选填"
                 @update:model-value="(value: number | undefined) => form.knowledge_pack_id = value || null">
        <el-option v-for="pack in packs" :key="pack.id" :value="pack.id" :label="pack.title" />
      </el-select>
      <label for="context-objective">分析目标</label><el-input id="context-objective" v-model="form.objective" type="textarea" :rows="3" maxlength="500" />
      <el-checkbox v-if="selectedId" v-model="form.archived">归档该上下文</el-checkbox>
      <div class="footer-actions"><el-button @click="open = false">取消</el-button><el-button native-type="submit" type="primary" :loading="saving">保存上下文</el-button></div>
    </form>
  </el-dialog>
</template>
