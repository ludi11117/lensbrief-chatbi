import { onMounted, onUnmounted, type Ref } from 'vue'
import { gsap } from 'gsap'

export function useEntrance(root: Ref<HTMLElement | undefined>) {
  let media: ReturnType<typeof gsap.matchMedia>
  onMounted(() => {
    media = gsap.matchMedia()
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from('[data-enter]', {
        y: 12, autoAlpha: 0, duration: 0.45, stagger: 0.07,
        ease: 'power2.out', clearProps: 'transform,opacity,visibility',
      })
    }, root.value)
  })
  onUnmounted(() => media?.revert())
}
