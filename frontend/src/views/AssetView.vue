<script setup lang="ts">
import { Download, FileText } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, blob, errorText, params } from '../api'

type Csv = { headers: string[]; rows: string[][]; total_rows: number }
const route = useRoute()
const id = Number(route.params.asset)
const report = typeof route.query.report === 'string' ? route.query.report : undefined
const version = typeof route.query.version === 'string' ? route.query.version : undefined
const filename = typeof route.query.filename === 'string' ? route.query.filename : '文件 ' + id
const path = '/assets/' + id
const source = ref('')
const mime = ref('')
const csv = ref<Csv>()
const busy = ref(false)
const error = ref('')
let disposed = false

onMounted(async () => {
  busy.value = true
  try {
    const file = await blob(path + '/content' + params({ report_id: report, version }))
    if (disposed) return
    mime.value = file.type
    if (mime.value.startsWith('text/csv')) csv.value = await api<Csv>(path + '/csv' + params({ report_id: report, version }))
    else source.value = URL.createObjectURL(file)
  } catch (err) { error.value = errorText(err) } finally { busy.value = false }
})
onUnmounted(() => {
  disposed = true
  if (source.value) URL.revokeObjectURL(source.value)
})
async function download() {
  try {
    const file = await blob(path + '/content' + params({ report_id: report, version, download: 'true' }))
    const href = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = href; link.download = filename; link.click()
    setTimeout(() => URL.revokeObjectURL(href), 1000)
  } catch (err) { error.value = errorText(err) }
}
</script>
<template>
  <RouterLink class="text-link" :to="report ? '/reports/' + report : '/reports'">返回报告</RouterLink>
  <div class="page-title split"><div><h1>文件预览</h1><p><FileText :size="16" /> {{ filename }}</p></div>
    <el-button :disabled="busy || !mime" @click="download"><Download :size="16" /> 下载文件</el-button></div>
  <section v-loading="busy" class="panel file-panel">
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <template v-if="csv">
      <p class="muted">显示 {{ csv.rows.length }} / {{ csv.total_rows }} 行</p>
      <div class="csv-scroll"><table class="csv-table"><thead><tr><th v-for="(name, idx) in csv.headers" :key="idx">{{ name }}</th></tr></thead>
        <tbody><tr v-for="(row, ridx) in csv.rows" :key="ridx"><td v-for="(value, idx) in row" :key="idx">{{ value }}</td></tr></tbody></table></div>
    </template>
    <img v-else-if="source && mime.startsWith('image/')" class="file-image" :src="source" :alt="filename" />
    <iframe v-else-if="source && mime === 'application/pdf'" class="pdf" :src="source" :title="filename" />
  </section>
</template>
