<script setup>
import ItineraryForm from '../components/ItineraryForm.vue'
import AiStatusBar from '../components/AiStatusBar.vue'
import TimelinePanel from '../components/Timeline/TimelinePanel.vue'
</script>

<template>
  <div class="grid grid-cols-12 gap-6">
    <aside class="col-span-12 lg:col-span-4">
      <div class="flex h-full flex-col gap-4">
        <ItineraryForm />
        <AiStatusBar />
      </div>
    </aside>
    <section class="col-span-12 lg:col-span-8">
      <TimelinePanel />
    </section>
  </div>
</template>

