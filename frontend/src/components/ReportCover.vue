<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { gsap } from 'gsap'
import { Pause, Play, ArrowUpRight } from '@lucide/vue'
const scope = ref<HTMLElement>()
const paused = ref(false)
// Frozen demo: seed.py, October 2026, analyst owner_id=1, SUM(revenue) GROUP BY channel.
const channels = [
  { name: '官网', value: 3308199 },
  { name: '电商平台', value: 3149647 },
  { name: '线下零售', value: 3134637 },
]
let media: ReturnType<typeof gsap.matchMedia>
let sequence: gsap.core.Timeline | undefined
let followX: ((value: number) => void) | undefined
let followY: ((value: number) => void) | undefined
function toggle() { paused.value = !paused.value; sequence?.paused(paused.value) }
function follow(event: PointerEvent) {
  if (event.pointerType !== 'mouse') return
  const box = scope.value!.getBoundingClientRect()
  followX?.(((event.clientX - box.left) / box.width - 0.5) * 10)
  followY?.(((event.clientY - box.top) / box.height - 0.5) * 8)
}
function reset() { followX?.(0); followY?.(0) }
onMounted(() => {
  media = gsap.matchMedia()
  media.add('(prefers-reduced-motion: no-preference)', () => {
    sequence = gsap.timeline({ paused: paused.value, repeat: -1, repeatDelay: 4, defaults: { ease: 'power3.out' } })
      .fromTo('.cover-bar', { scaleX: 0 }, { scaleX: 1, duration: 1.1, stagger: 0.15 })
      .fromTo('.cover-amount', { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, duration: 0.6, stagger: 0.12 }, 0.45)
      .fromTo('.cover-rule', { scaleX: 0 }, { scaleX: 1, duration: 0.8 }, 0)
      .to({}, { duration: 1.5 })
  }, scope.value)
  media.add('(prefers-reduced-motion: no-preference) and (hover: hover) and (pointer: fine)', () => {
    followX = gsap.quickTo('.report-cover-sheet', 'x', { duration: 0.7, ease: 'power3.out' })
    followY = gsap.quickTo('.report-cover-sheet', 'y', { duration: 0.7, ease: 'power3.out' })
    return () => { followX = undefined; followY = undefined }
  }, scope.value)
})
onUnmounted(() => media?.revert())
</script>
<template>
  <div ref="scope" class="report-cover" @pointermove="follow" @pointerleave="reset">
    <article class="report-cover-sheet" aria-label="十月渠道销售额演示报告">
      <div class="cover-top"><span>DEMO REPORT / 2026.10</span><button type="button" class="flow-control" :aria-label="paused ? '播放图表动画' : '暂停图表动画'" :aria-pressed="paused" @click="toggle"><Play v-if="paused" :size="14" /><Pause v-else :size="14" /></button></div>
      <h2>十月渠道表现复盘<ArrowUpRight :size="28" /></h2>
      <div class="cover-rule"></div>
      <div class="cover-total"><span>销售额 / 本人范围</span><strong>¥9,592,483</strong></div>
      <div v-for="channel in channels" :key="channel.name" class="cover-row">
        <div><span>{{ channel.name }}</span><b class="cover-amount">¥{{ channel.value.toLocaleString('en-US') }}</b></div>
        <div class="cover-track"><span class="cover-bar" :style="{ width: `${channel.value / channels[0]!.value * 100}%` }"></span></div>
      </div>
      <p class="cover-foot">销售额含后续退款订单，不等于净收入。</p>
    </article>
  </div>
</template>
