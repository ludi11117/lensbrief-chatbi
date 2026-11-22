<script setup lang="ts">
import { Download, FileText } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, blob, errorText, params } from '../api'
import { downloadBlob } from '../download'
import type { Asset } from '../types'

type Csv = { headers: string[]; rows: string[][]; total_rows: number }
const route = useRoute()
const id = Number(route.params.asset)
const report = typeof route.query.report === 'string' ? route.query.report : undefined
const version = typeof route.query.version === 'string' ? route.query.version : undefined
const path = '/assets/' + id
const access = params({ report_id: report, version })
const attachment = ref<Asset>()
const filename = computed(() => attachment.value?.filename ?? '文件 ' + id)
const source = ref('')
const csv = ref<Csv>()
const currentPage = ref(1)
const pageSize = 25
const firstRow = computed(() => (currentPage.value - 1) * pageSize + 1)
const busy = ref(false)
const error = ref('')
let disposed = false

async function loadCsv(number: number) {
  busy.value = true
  error.value = ''
  try {
    const query = params({ report_id: report, version, limit: pageSize, offset: (number - 1) * pageSize })
    csv.value = await api<Csv>(path + '/csv' + query)
    currentPage.value = number
  } catch (err) { error.value = errorText(err) } finally { busy.value = false }
}

onMounted(async () => {
  busy.value = true
  try {
    const metadata = await api<Asset>(path + access)
    if (disposed) return
    attachment.value = metadata
    if (metadata.mime === 'text/csv') {
      await loadCsv(1)
    } else {
      const file = await blob(path + '/content' + access)
      if (!disposed) source.value = URL.createObjectURL(file)
    }
  } catch (err) { error.value = errorText(err) } finally { busy.value = false }
})
onUnmounted(() => {
  disposed = true
  if (source.value) URL.revokeObjectURL(source.value)
})
async function download() {
  try {
    const file = await blob(path + '/content' + params({ report_id: report, version, download: 'true' }))
    downloadBlob(file, filename.value)
  } catch (err) { error.value = errorText(err) }
}
</script>
<template>
  <RouterLink class="text-link" :to="report ? { name: 'report', params: { id: report }, query: { version } } : '/reports'">返回报告</RouterLink>
  <div class="page-title split"><div><h1>文件预览</h1><p><FileText :size="16" /> {{ filename }}</p></div>
    <el-button :disabled="busy || !attachment" @click="download"><Download :size="16" /> 下载文件</el-button></div>
  <section v-loading="busy" class="panel file-panel">
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="csv">
      <p class="muted"><template v-if="csv.rows.length">第 {{ firstRow }}<template v-if="csv.rows.length > 1">–{{ firstRow + csv.rows.length - 1 }}</template> 行，</template>共 {{ csv.total_rows }} 行</p>
      <div class="csv-scroll"><table class="csv-table"><thead><tr><th v-for="(name, idx) in csv.headers" :key="idx">{{ name }}</th></tr></thead>
        <tbody><tr v-for="(row, ridx) in csv.rows" :key="ridx"><td v-for="(value, idx) in row" :key="idx">{{ value }}</td></tr></tbody></table></div>
      <el-pagination v-if="csv.total_rows > pageSize" class="pagination" :current-page="currentPage" :page-size="pageSize"
                     :total="csv.total_rows" :disabled="busy" layout="prev, pager, next" @update:current-page="loadCsv" />
    </template>
    <img v-else-if="source && attachment?.mime.startsWith('image/')" class="file-image" :src="source" :alt="filename" />
    <iframe v-else-if="source && attachment?.mime === 'application/pdf'" class="pdf" :src="source" :title="filename" />
  </section>
</template>
