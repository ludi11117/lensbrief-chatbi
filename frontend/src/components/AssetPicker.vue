<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, errorText, params } from '../api'
import type { Asset, Page } from '../types'
import WorkspaceTabLink from './WorkspaceTabLink.vue'

defineProps<{ attached: Asset[] }>()
const emit = defineEmits<{ select: [asset: Asset]; close: [] }>()
const files = ref<Asset[]>([])
const current = ref(1)
const total = ref(0)
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const appliedKeyword = ref('')
const pageSize = 8

async function load() {
  loading.value = true
  error.value = ''
  try {
    const page = await api<Page<Asset>>('/assets' + params({
      q: appliedKeyword.value, limit: pageSize, offset: (current.value - 1) * pageSize,
    }))
    files.value = page.items
    total.value = page.total
  } catch (err) { error.value = errorText(err) } finally { loading.value = false }
}
function search() {
  appliedKeyword.value = keyword.value.trim()
  changePage(1)
}
function changePage(number: number) {
  current.value = number
  void load()
}
onMounted(load)
</script>

<template>
  <el-dialog :model-value="true" title="选择已上传的文件" width="min(620px, 94vw)" @close="emit('close')">
    <form class="toolbar" @submit.prevent="search">
      <el-input v-model="keyword" class="search-input" aria-label="按文件名搜索" placeholder="按文件名搜索" maxlength="200" clearable :disabled="loading" />
      <el-button native-type="submit" :disabled="loading">搜索文件</el-button>
    </form>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-table v-else v-loading="loading" :data="files" :empty-text="appliedKeyword ? '没有匹配的文件' : '还没有上传文件'">
      <el-table-column prop="filename" label="文件名" min-width="160" show-overflow-tooltip />
      <el-table-column label="大小" width="86">
        <template #default="{ row }">{{ row.size_bytes < 1024 ? row.size_bytes + ' B' : (row.size_bytes / 1024).toFixed(1) + ' KiB' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <div class="table-links">
            <WorkspaceTabLink :to="{ name: 'asset', params: { asset: row.id } }">预览</WorkspaceTabLink>
            <el-button v-if="attached.some(file => file.id === row.id)" text disabled>已添加</el-button>
            <el-button v-else type="primary" link :disabled="loading" @click="emit('select', row)">添加</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-if="total > pageSize && !error" :current-page="current" class="pagination"
                   :disabled="loading" :total="total" :page-size="pageSize" layout="prev, pager, next" @update:current-page="changePage" />
  </el-dialog>
</template>
