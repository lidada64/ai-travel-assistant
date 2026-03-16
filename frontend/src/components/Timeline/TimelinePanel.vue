<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useItineraryStore } from '../../stores/itinerary'
import { useHorizontalWheelScroll } from '../../composables/useHorizontalWheelScroll'
import TimelineNode from './TimelineNode.vue'

const store = useItineraryStore()
const { ui, raw, request } = storeToRefs(store)

const viewportRef = ref(null)
const { scrollByStep } = useHorizontalWheelScroll(viewportRef)

function isValidDateInput(value) {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
}

function dayCountFromRange(start, end) {
  if (!isValidDateInput(start) || !isValidDateInput(end)) return null
  const startMs = Date.parse(`${start}T00:00:00`)
  const endMs = Date.parse(`${end}T00:00:00`)
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null
  if (endMs < startMs) return null
  return Math.floor((endMs - startMs) / 86_400_000) + 1
}

function formatBudget(min, max, currency) {
  const nMin = Number(min)
  const nMax = Number(max)
  if (!Number.isFinite(nMin) || !Number.isFinite(nMax) || nMin < 0 || nMax < 0 || nMin > nMax) return '--'
  const unit = String(currency || '').trim()
  const fmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 })
  const left = fmt.format(nMin)
  const right = fmt.format(nMax)
  return unit ? `${unit} ${left}–${right}` : `${left}–${right}`
}

const groups = computed(() => {
  const out = []
  let current = null
  for (const item of store.timelineItems) {
    if (item.type === 'marker') {
      if (current) out.push(current)
      current = { dateKey: item.dateKey, marker: item, items: [] }
      continue
    }
    if (!current) {
      current = { dateKey: item.dateKey, marker: null, items: [] }
    }
    current.items.push(item)
  }
  if (current) out.push(current)
  return out
})

const hasData = computed(() => groups.value.some((g) => g.items.length > 0))

const summary = computed(() => {
  const r = raw.value ?? {}
  const flights = Array.isArray(r.flights) ? r.flights : []
  const hotels = Array.isArray(r.hotels) ? r.hotels : []
  const views = Array.isArray(r.views) ? r.views : []

  const req = request.value ?? {}
  const dest = Array.isArray(req.destination) ? req.destination : []
  const budget = req.budget ?? {}
  const time = req.time ?? {}

  const daysFromRequest = dayCountFromRange(time.start_date, time.end_date)
  const daysFromTimeline = groups.value.filter((g) => g.items.length > 0).length || null

  return {
    budgetRange: formatBudget(budget.min, budget.max, budget.currency),
    destinations: dest.length,
    days: daysFromRequest ?? daysFromTimeline ?? '--',
    flights: flights.length,
    hotels: hotels.length,
    views: views.length,
  }
})

const scrollLeft = () => {
  const el = viewportRef.value
  if (!el) return
  scrollByStep(-el.clientWidth * 0.8)
}

const scrollRight = () => {
  const el = viewportRef.value
  if (!el) return
  scrollByStep(el.clientWidth * 0.8)
}

const canScrollLeft = ref(false)
const canScrollRight = ref(false)

const updateScrollButtons = () => {
  const el = viewportRef.value
  if (!el) {
    canScrollLeft.value = false
    canScrollRight.value = false
    return
  }
  const max = Math.max(0, el.scrollWidth - el.clientWidth)
  canScrollLeft.value = el.scrollLeft > 1
  canScrollRight.value = el.scrollLeft < max - 1
}

onMounted(() => {
  const el = viewportRef.value
  if (!el) return
  updateScrollButtons()
  el.addEventListener('scroll', updateScrollButtons, { passive: true })
  window.addEventListener('resize', updateScrollButtons, { passive: true })
})

onBeforeUnmount(() => {
  const el = viewportRef.value
  if (el) el.removeEventListener('scroll', updateScrollButtons)
  window.removeEventListener('resize', updateScrollButtons)
})

watch(
  () => [ui.value.loading, raw.value, request.value],
  async () => {
    await nextTick()
    updateScrollButtons()
  },
  { deep: false },
)
</script>

<template>
  <section class="relative flex h-[640px] flex-col border border-[var(--line)] bg-[rgba(10,10,10,0.6)]">
    <div class="flex items-center justify-between border-b border-[var(--line)] px-4 py-3">
      <div class="text-[11px] uppercase tracking-[0.24em] text-[var(--dim)]">Timeline Canvas</div>
      <div class="text-[11px] uppercase tracking-[0.22em] text-[rgba(244,244,245,0.45)]">
        <span v-if="ui.loading">RUNNING</span>
        <span v-else>READY</span>
      </div>
    </div>

    <div class="border-b border-[var(--line)] px-4 py-3">
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <div class="border border-[var(--line)] bg-[rgba(10,10,10,0.62)] px-3 py-2">
          <div class="mono text-[10px] uppercase tracking-[0.22em] text-[rgba(244,244,245,0.48)]">Budget Range</div>
          <div class="mt-1 text-[13px] tracking-[0.01em] text-[rgba(244,244,245,0.9)]">{{ summary.budgetRange }}</div>
        </div>
        <div class="border border-[var(--line)] bg-[rgba(10,10,10,0.62)] px-3 py-2">
          <div class="mono text-[10px] uppercase tracking-[0.22em] text-[rgba(244,244,245,0.48)]">Trip</div>
          <div class="mt-1 text-[13px] tracking-[0.01em] text-[rgba(244,244,245,0.9)]">
            {{ summary.days }} days · {{ summary.destinations }} destinations
          </div>
        </div>
        <div class="border border-[var(--line)] bg-[rgba(10,10,10,0.62)] px-3 py-2">
          <div class="mono text-[10px] uppercase tracking-[0.22em] text-[rgba(244,244,245,0.48)]">Items</div>
          <div class="mt-1 text-[13px] tracking-[0.01em] text-[rgba(244,244,245,0.9)]">
            {{ summary.flights }} flights · {{ summary.hotels }} hotels · {{ summary.views }} views
          </div>
        </div>
      </div>
    </div>

    <div class="relative flex-1">
      <div ref="viewportRef" class="no-scrollbar h-full cursor-grab select-none touch-pan-y overflow-x-auto overflow-y-hidden active:cursor-grabbing">
        <div class="relative h-full w-max min-w-full px-10">
          <div
            class="pointer-events-none absolute left-0 right-0 top-1/2 -translate-y-1/2 border-t border-dashed border-[var(--line)]"
          ></div>

        <div v-if="ui.loading" class="relative flex h-full items-stretch gap-16 py-12">
          <div v-for="n in 3" :key="n" class="relative flex items-center gap-10 pr-10">
            <div class="absolute left-0 top-1/2 h-[1px] w-full -translate-y-1/2 bg-transparent"></div>
            <div class="relative h-[170px] w-[120px]">
              <div
                class="absolute left-1/2 top-1/2 h-[28px] w-[80px] -translate-x-1/2 -translate-y-1/2 border border-[var(--line)] bg-[rgba(10,10,10,0.65)]"
              ></div>
            </div>
            <div v-for="k in 5" :key="k" class="relative h-[170px] w-[96px]">
              <div
                class="absolute left-1/2 top-1/2 h-[56px] w-[56px] -translate-x-1/2 -translate-y-1/2 border border-[var(--line)] bg-[rgba(10,10,10,0.55)]"
              ></div>
            </div>
          </div>
        </div>

        <div v-else-if="!hasData" class="grid h-full place-items-center py-12">
          <div class="max-w-[520px] text-center">
            <div class="text-[12px] uppercase tracking-[0.28em] text-[rgba(244,244,245,0.55)]">No Data</div>
            <div class="mt-2 text-[13px] text-[rgba(244,244,245,0.62)]">
              Generate an itinerary to render flights, hotel boundaries, and views.
            </div>
          </div>
        </div>

          <div v-else class="relative flex h-full items-stretch gap-16 py-12">
            <div v-for="g in groups" :key="g.dateKey" class="relative flex items-center gap-10 pr-10">
              <TimelineNode v-if="g.marker" :item="g.marker" />
              <TimelineNode v-for="it in g.items" :key="it.id" :item="it" />
            </div>
          </div>
        </div>
      </div>

      <button
        type="button"
        :disabled="!canScrollLeft"
        class="absolute left-3 top-1/2 z-20 -translate-y-1/2 border border-[var(--line)] bg-[rgba(10,10,10,0.52)] px-3 py-2 text-[12px] text-[rgba(244,244,245,0.62)] opacity-60 hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-20"
        @click="scrollLeft"
      >
        ‹
      </button>
      <button
        type="button"
        :disabled="!canScrollRight"
        class="absolute right-3 top-1/2 z-20 -translate-y-1/2 border border-[var(--line)] bg-[rgba(10,10,10,0.52)] px-3 py-2 text-[12px] text-[rgba(244,244,245,0.62)] opacity-60 hover:opacity-100 disabled:cursor-not-allowed disabled:opacity-20"
        @click="scrollRight"
      >
        ›
      </button>
    </div>
  </section>
</template>

