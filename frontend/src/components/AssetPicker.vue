<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorText, params } from '../api'
import type { Asset, Page } from '../types'

defineProps<{ attached: Asset[] }>()
const emit = defineEmits<{ select: [asset: Asset]; close: [] }>()
const files = ref<Asset[]>([])
const current = ref(1)
const total = ref(0)
const loading = ref(false)
const error = ref('')
const pageSize = 8

async function load() {
  loading.value = true
  error.value = ''
  try {
    const page = await api<Page<Asset>>('/assets' + params({ limit: pageSize, offset: (current.value - 1) * pageSize }))
    files.value = page.items
    total.value = page.total
  } catch (err) { error.value = errorText(err) } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <el-dialog :model-value="true" title="选择已上传的文件" width="min(560px, 94vw)" @close="emit('close')">
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-table v-else v-loading="loading" :data="files" empty-text="还没有上传文件">
      <el-table-column prop="filename" label="文件名" min-width="160" show-overflow-tooltip />
      <el-table-column label="大小" width="86">
        <template #default="{ row }">{{ (row.size_bytes / 1024).toFixed(1) }} KiB</template>
      </el-table-column>
      <el-table-column width="88">
        <template #default="{ row }">
          <el-button v-if="attached.some(file => file.id === row.id)" text disabled>已添加</el-button>
          <el-button v-else type="primary" link :disabled="loading" @click="emit('select', row)">添加</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="total > pageSize && !error" v-model:current-page="current" class="pagination"
                   :disabled="loading" :total="total" :page-size="pageSize" layout="prev, pager, next" @current-change="load" />
  </el-dialog>
</template>
