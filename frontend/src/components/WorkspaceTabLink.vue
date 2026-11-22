<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { RouteLocationRaw } from 'vue-router'

defineProps<{ to: RouteLocationRaw }>()

function openTab(href: string) {
  const tab = window.open('about:blank', '_blank')
  if (!tab) {
    ElMessage.warning('浏览器拦截了新标签页。可复制链接后打开。')
    return
  }
  // The new tab inherits session storage when it opens. Detach the opener before navigation.
  tab.opener = null
  tab.location.replace(new URL(href, window.location.href).href)
}
</script>

<template>
  <RouterLink :to="to" custom v-slot="{ href }">
    <a :href="href" class="text-link" target="_blank" rel="noopener" @click.prevent="openTab(href)"><slot /></a>
  </RouterLink>
</template>
