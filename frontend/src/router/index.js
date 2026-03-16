import { createRouter, createWebHistory } from 'vue-router'

const ItineraryBuilder = () => import('../pages/ItineraryBuilder.vue')
const MapView = () => import('../pages/MapView.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'builder', component: ItineraryBuilder },
    { path: '/map', name: 'map', component: MapView },
  ],
})

