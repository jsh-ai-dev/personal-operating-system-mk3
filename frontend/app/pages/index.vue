<script setup lang="ts">
interface HealthResponse {
  status: string
  mongodb: string
  qdrant: string
}

const api = useApi()
const { data: health, error } = await useAsyncData('health', () =>
  api<HealthResponse>('/api/v1/health'),
)
</script>

<template>
  <main>
    <h1>Personal Operating System mk3</h1>

    <section>
      <h2>Backend Status</h2>
      <div v-if="health">
        <p>API <span class="ok">{{ health.status }}</span></p>
        <p>MongoDB <span class="ok">{{ health.mongodb }}</span></p>
        <p>Qdrant <span class="ok">{{ health.qdrant }}</span></p>
      </div>
      <div v-else-if="error">
        <p class="error">Backend에 연결할 수 없습니다.</p>
        <pre>{{ error.message }}</pre>
      </div>
    </section>
  </main>
</template>

<style scoped>
main {
  max-width: 600px;
  margin: 60px auto;
  padding: 0 24px;
  font-family: monospace;
}
h1 { font-size: 1.4rem; margin-bottom: 32px; }
h2 { font-size: 1rem; margin-bottom: 12px; color: #666; }
p { margin: 6px 0; }
.ok { color: #22c55e; font-weight: bold; }
.error { color: #ef4444; }
pre { font-size: 0.8rem; color: #999; }
</style>
