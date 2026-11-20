<script setup lang="ts">
import { Search } from 'lucide-vue-next'
import { statusText } from '../types'
defineProps<{ keyword: string; status: string }>()
const emit = defineEmits<{
  'update:keyword': [value: string]; 'update:status': [value: string]; search: []; reset: []
}>()
</script>
<template>
  <form class="toolbar" @submit.prevent="emit('search')">
    <el-input :model-value="keyword" @update:model-value="emit('update:keyword', $event)" clearable
              aria-label="搜索报告" placeholder="搜索报告名称或描述" class="search-input">
      <template #prefix><Search :size="17" /></template>
    </el-input>
    <el-select :model-value="status" @update:model-value="emit('update:status', $event)"
               aria-label="报告状态" class="status-select">
      <el-option label="全部状态" value="" />
      <el-option v-for="(label, value) in statusText" :key="value" :label="label" :value="value" />
    </el-select>
    <el-button native-type="submit">筛选</el-button>
    <el-button text @click="emit('reset')">重置</el-button>
  </form>
</template>
