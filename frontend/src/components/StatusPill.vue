<script setup lang="ts">
import { statusText, type Status } from '../types'
defineProps<{ status: Status }>()
</script>
<template><span class="status-pill" :class="status">{{ statusText[status] }}</span></template>
