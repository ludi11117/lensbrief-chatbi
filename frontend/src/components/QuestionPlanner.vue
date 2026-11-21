<script setup lang="ts">
import { MessageSquareText } from 'lucide-vue-next'
import { onBeforeUnmount, ref } from 'vue'
import { api, errorText } from '../api'
import { scopeText, type QueryPlan } from '../types'

const props = defineProps<{ datasetId: number; contextId: number | null; disabled?: boolean }>()
const emit = defineEmits<{ apply: [plan: QueryPlan]; planning: [active: boolean] }>()
const question = ref('')
const error = ref('')
const resolved = ref<QueryPlan | null>(null)
const busy = ref(false)
let requestId = 0

function clearFeedback() {
  error.value = ''
  resolved.value = null
}
onBeforeUnmount(() => {
  requestId++
  if (busy.value) emit('planning', false)
})
async function resolve() {
  if (busy.value || props.disabled || question.value.trim().length < 3) return
  const id = ++requestId
  busy.value = true
  emit('planning', true)
  clearFeedback()
  try {
    const plan = await api<QueryPlan>('/queries/plan', { method: 'POST', body: JSON.stringify({
      dataset_id: props.datasetId, context_id: props.contextId, question: question.value,
    }) })
    if (requestId === id) {
      emit('apply', plan)
      resolved.value = plan
    }
  } catch (err) {
    if (requestId === id) error.value = errorText(err)
  } finally {
    if (requestId === id) {
      busy.value = false
      emit('planning', false)
    }
  }
}
</script>

<template>
  <form class="question-planner" @submit.prevent="resolve">
    <label for="query-question"><MessageSquareText :size="16" /> 自然语言提问</label>
    <el-input id="query-question" v-model="question" maxlength="200" :disabled="busy || disabled"
              placeholder="2026年10月按渠道看销售额" @input="clearFeedback" />
    <p v-if="contextId" class="muted">如已有成功查询，可追问「改按产品」或「改看退款率」。</p>
    <el-button type="primary" plain native-type="submit" :loading="busy"
               :disabled="disabled || question.trim().length < 3">解析问题</el-button>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-if="resolved" class="plan-feedback" aria-live="polite">
      <strong>已填入查询条件。请核对后运行查询。</strong>
      <p>{{ resolved.source === 'llm' ? '模型辅助解析' : '规则解析' }} · {{ scopeText[resolved.scope] }}范围</p>
      <p v-for="note in resolved.notes" :key="note">{{ note }}</p>
    </div>
  </form>
</template>
