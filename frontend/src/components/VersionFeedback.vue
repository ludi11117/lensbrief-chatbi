<script setup lang="ts">
import { MessageSquareText } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
import { api, errorText, params } from '../api'
import { dateText, type Feedback, type Page } from '../types'

const props = defineProps<{ reportPath: string; version: number; archived: boolean }>()
const path = props.reportPath + '/versions/' + props.version + '/feedback'
const pageSize = 10
const current = ref(1)
const entries = ref<Feedback[]>([])
const total = ref(0)
const loading = ref(false)
const saving = ref(false)
const body = ref('')
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await api<Page<Feedback>>(path + params({ limit: pageSize, offset: (current.value - 1) * pageSize }))
    entries.value = response.items
    total.value = response.total
  } catch (err) { error.value = errorText(err) } finally { loading.value = false }
}
onMounted(load)

async function submit() {
  if (!body.value.trim() || loading.value || saving.value || props.archived) return
  saving.value = true
  error.value = ''
  try {
    await api<Feedback>(path, { method: 'POST', body: JSON.stringify({ body: body.value }) })
    body.value = ''
    current.value = 1
    await load()
  } catch (err) { error.value = errorText(err) } finally { saving.value = false }
}
</script>

<template>
  <section class="version-feedback">
    <div class="section-head"><h3><MessageSquareText :size="17" /> v{{ version }} 版本反馈</h3><span class="muted">{{ total }} 条反馈</span></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading">
      <p v-if="!entries.length && !loading" class="muted">此版本暂无反馈。</p>
      <ul v-else class="feedback-list">
        <li v-for="item in entries" :key="item.id">
          <div class="section-head"><strong>{{ item.author_name }}</strong><time :datetime="item.created_at">{{ dateText(item.created_at) }}</time></div>
          <p>{{ item.body }}</p>
        </li>
      </ul>
    </div>
    <div v-if="total > pageSize" class="pagination">
      <el-pagination v-model:current-page="current" :page-size="pageSize" :total="total"
                     layout="prev, pager, next" :disabled="loading || saving" @current-change="load" />
    </div>
    <form v-if="!archived" class="feedback-form" @submit.prevent="submit">
      <el-input v-model="body" aria-label="反馈内容" placeholder="记录口径问题或后续行动" type="textarea"
                :rows="2" maxlength="1200" :disabled="saving" />
      <el-button type="primary" native-type="submit" :loading="saving" :disabled="loading || !body.trim()">提交反馈</el-button>
    </form>
  </section>
</template>
