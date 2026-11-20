<script setup lang="ts">
import type { Status } from '../types'
defineProps<{ status: Status; allowed: Record<string, boolean>; loading?: boolean }>()
const emit = defineEmits<{ edit: []; publish: []; archive: []; remove: [] }>()
</script>
<template>
  <div class="action-row">
    <el-button v-if="allowed.delete" plain type="danger" :disabled="loading" @click="emit('remove')">删除</el-button>
    <el-button v-if="allowed.archive && status === 'published'" :disabled="loading" @click="emit('archive')">归档</el-button>
    <el-button v-if="allowed.edit && status !== 'archived'" :disabled="loading" @click="emit('edit')">编辑报告</el-button>
    <el-button v-if="allowed.publish && status !== 'archived'" type="primary" :loading="loading" @click="emit('publish')">
      {{ status === 'draft' ? '发布报告' : '发布新版本' }}
    </el-button>
  </div>
</template>
