<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useItineraryStore } from '../stores/itinerary'

const store = useItineraryStore()
const { ai } = storeToRefs(store)

const viewportRef = ref(null)
const pinned = ref(true)

const cursor = computed(() => (ai.value.running ? '▮' : ' '))

const onScroll = () => {
  const el = viewportRef.value
  if (!el) return
  const threshold = 8
  pinned.value = el.scrollTop + el.clientHeight >= el.scrollHeight - threshold
}

const scrollToBottomIfPinned = async () => {
  if (!pinned.value) return
  await nextTick()
  const el = viewportRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

watch(
  () => ai.value.lines.length,
  async () => {
    await scrollToBottomIfPinned()
  },
)

onMounted(() => {
  scrollToBottomIfPinned()
})
</script>

<template>
  <div class="border border-[var(--line)] bg-[rgba(10,10,10,0.72)]">
    <div class="flex items-center justify-between border-b border-[var(--line)] px-3 py-2">
      <div class="mono text-[11px] uppercase tracking-[0.22em] text-[var(--dim)]">AI Terminal</div>
      <div class="mono text-[10px] tracking-[0.18em] text-[var(--dim)]">
        <span v-if="!pinned">SCROLL LOCK</span>
        <span v-else>LIVE</span>
      </div>
    </div>
    <div
      ref="viewportRef"
      class="no-scrollbar mono max-h-[168px] overflow-y-auto px-3 py-2 text-[12px] leading-5 text-[var(--muted)]"
      @scroll="onScroll"
    >
      <div v-for="line in ai.lines" :key="line.id" class="whitespace-pre-wrap break-words">
        <span
          :class="[
            line.level === 'error' ? 'text-[rgba(244,244,245,0.92)]' : '',
            line.level === 'system' ? 'text-[rgba(244,244,245,0.82)]' : '',
          ]"
          >{{ line.text }}</span
        >
      </div>
      <div class="whitespace-pre-wrap break-words">
        <span class="cursor" :class="{ running: ai.running }">{{ cursor }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cursor.running {
  animation: blink 1.1s steps(2, end) infinite;
}
@keyframes blink {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}
</style>

