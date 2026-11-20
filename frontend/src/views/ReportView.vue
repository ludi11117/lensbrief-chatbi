<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { FileText, GitCompareArrows, History } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, api, errorText, params } from '../api'
import QueryPreview from '../components/QueryResult.vue'
import ReportActions from '../components/ReportActions.vue'
import StatusPill from '../components/StatusPill.vue'
import { dateText, type Page, type Report, type Snapshot, type VersionDiff, type VersionRow } from '../types'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const path = '/reports/' + id
const report = ref<Report>()
const versions = ref<VersionRow[]>([])
const versionsTotal = ref(0)
const historyPage = ref(1)
const selected = ref<Snapshot | null>(null)
const selectedNumber = ref<number | null>(null)
const compareOpen = ref(false)
const base = ref<number>()
const target = ref<number>()
const comparison = ref<VersionDiff>()
const compareError = ref('')
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const errorCode = ref<number>()
const showing = computed(() => selected.value ?? report.value)
const labels: Record<string, string> = { title: '标题', description: '摘要', dataset_id: '数据集', query_id: '查询记录', asset_ids: '附件 ID' }
const format = (value: unknown) => Array.isArray(value) ? value.join('、') || '—' : String(value ?? '—')
let previewRequest = 0

async function loadVersions() {
  const history = await api<Page<VersionRow>>(path + '/versions' + params({ limit: 10, offset: (historyPage.value - 1) * 10 }))
  versions.value = history.items
  versionsTotal.value = history.total
}
async function changeHistory() {
  try { await loadVersions() } catch (err) { error.value = errorText(err) }
}
async function load() {
  loading.value = true
  error.value = ''
  try { report.value = await api<Report>(path); await loadVersions() }
  catch (err) { error.value = errorText(err); errorCode.value = err instanceof ApiError ? err.status : undefined }
  finally { loading.value = false }
}
onMounted(load)

async function preview(number: number | null) {
  const request = ++previewRequest
  if (number === null) { selected.value = null; selectedNumber.value = null; return }
  error.value = ''
  try {
    const snapshot = await api<Snapshot>(path + '/versions/' + number)
    if (request === previewRequest) { selected.value = snapshot; selectedNumber.value = number }
  } catch (err) { if (request === previewRequest) error.value = errorText(err) }
}
function openCompare() {
  target.value = report.value?.current_version ?? undefined
  base.value = target.value ? target.value - 1 : undefined
  compareOpen.value = true
  comparison.value = undefined
  compareError.value = ''
}
async function compare() {
  compareError.value = ''
  comparison.value = undefined
  if (!base.value || !target.value || base.value === target.value) { compareError.value = '请输入两个不同的版本号。'; return }
  try { comparison.value = await api<VersionDiff>(path + '/versions/diff' + params({ base: base.value, target: target.value })) }
  catch (err) { compareError.value = errorText(err) }
}
async function perform(action: 'publish' | 'archive' | 'remove' | 'rollback', number?: number) {
  const prompts = {
    publish: '发布会将当前工作稿保存为一个新版本。',
    archive: '归档后仍可查看历史版本，编辑及发布将关闭。',
    remove: '删除后此报告将从报告中心移除。',
    rollback: '将 v' + number + ' 的内容恢复为一个新的发布版本，保留现有版本。',
  }
  try { await ElMessageBox.confirm(prompts[action], '确认操作', { confirmButtonText: '确认', cancelButtonText: '取消' }) }
  catch { return }
  busy.value = true
  error.value = ''
  try {
    if (action === 'remove') {
      await api(path, { method: 'DELETE' })
      ElMessage.success('报告已删除')
      await router.push('/reports')
      return
    }
    const suffix = action === 'rollback' ? 'rollback/' + number : action
    await api(path + '/' + suffix, { method: 'POST' })
    ElMessage.success({ publish: '已发布新版本', archive: '报告已归档', rollback: '已回滚并发布新版本' }[action])
    historyPage.value = 1
    await preview(null)
    await load()
  } catch (err) { error.value = errorText(err) } finally { busy.value = false }
}
</script>
<template>
  <RouterLink class="text-link" to="/reports">返回报告中心</RouterLink>
  <el-alert v-if="error" class="page-alert" :title="errorCode ? errorCode + ' · ' + error : error" type="error" show-icon :closable="false" />
  <div v-loading="loading" class="detail-page">
    <template v-if="report && showing">
      <div class="page-title split">
        <div><div class="inline"><StatusPill :status="report.status" /><span v-if="report.current_version" class="muted">当前发布 v{{ report.current_version }}</span></div>
          <h1>{{ report.title }}</h1><p>更新于 {{ dateText(report.updated_at) }}<span v-if="report.has_unpublished_changes"> · 工作稿有未发布更改</span></p></div>
        <ReportActions :status="report.status" :allowed="report.allowed" :loading="busy" @edit="router.push(path + '/edit')" @publish="perform('publish')" @archive="perform('archive')" @remove="perform('remove')" />
      </div>
      <div class="detail-grid">
        <article class="panel">
          <div class="section-head"><h2>报告预览</h2><span class="version-label">{{ selectedNumber ? '历史版本 v' + selectedNumber : report.status === 'archived' ? '归档版本' : '当前工作稿' }}</span></div>
          <h3 class="preview-title">{{ showing.title }}</h3>
          <p v-if="showing.description" class="preview-description">{{ showing.description }}</p>
          <QueryPreview v-if="showing.query" :result="showing.query" />
          <div class="report-body">{{ showing.content || '暂无正文。' }}</div>
          <div v-if="showing.assets.length" class="attachment-list">
            <h3>附件</h3>
            <RouterLink v-for="file in showing.assets" :key="file.id" class="attachment"
                        :to="{ name: 'asset', params: { asset: file.id }, query: {
                          report: id, version: selectedNumber ?? undefined, filename: file.filename,
                        } }">
              <FileText :size="17" /><span>{{ file.filename }}</span><strong>预览</strong>
            </RouterLink>
          </div>
        </article>
        <section class="panel version-panel">
          <div class="section-head"><h2><History :size="19" /> 版本记录</h2><el-button v-if="versionsTotal >= 2" size="small" @click="openCompare"><GitCompareArrows :size="15" /> 对比版本</el-button></div>
          <el-empty v-if="!versions.length" description="发布报告后将生成版本" :image-size="60" />
          <template v-else>
            <el-button v-if="selectedNumber" text type="primary" @click="preview(null)">返回当前内容</el-button>
            <div v-for="version in versions" :key="version.number" class="version-item" :class="{ selected: selectedNumber === version.number }">
              <button class="version-button" type="button" @click="preview(version.number)">
                <strong>v{{ version.number }} <span v-if="version.number === report.current_version" class="status-pill published">当前</span></strong>
                <small>{{ dateText(version.created_at) }} · {{ version.created_by_name }}</small>
                <small v-if="version.restored_from">恢复自 v{{ version.restored_from }}</small>
              </button>
              <el-button v-if="report.allowed.rollback && report.status === 'published' && version.number !== report.current_version" text type="primary" :disabled="busy" @click="perform('rollback', version.number)">回滚</el-button>
            </div>
            <el-pagination v-if="versionsTotal > 10" v-model:current-page="historyPage" :total="versionsTotal" :page-size="10" layout="prev, pager, next" @current-change="changeHistory" />
          </template>
        </section>
      </div>
    </template>
  </div>
  <el-dialog v-model="compareOpen" title="版本元数据对比" width="min(620px, 94vw)">
    <div class="compare-controls"><label>基准版本 <el-input-number v-model="base" :min="1" :max="report?.current_version ?? 1" /></label>
      <label>目标版本 <el-input-number v-model="target" :min="1" :max="report?.current_version ?? 1" /></label>
      <el-button type="primary" @click="compare">开始对比</el-button></div>
    <el-alert v-if="compareError" :title="compareError" type="error" :closable="false" />
    <template v-if="comparison">
      <el-table v-if="comparison.changes.length" :data="comparison.changes">
        <el-table-column label="字段"><template #default="{ row }">{{ labels[row.field] || row.field }}</template></el-table-column>
        <el-table-column label="原值"><template #default="{ row }">{{ format(row.before) }}</template></el-table-column>
        <el-table-column label="新值"><template #default="{ row }">{{ format(row.after) }}</template></el-table-column>
      </el-table>
      <p v-else>元数据相同。</p>
      <p>正文{{ comparison.content_changed ? '有变化' : '相同' }}。</p>
    </template>
  </el-dialog>
</template>
