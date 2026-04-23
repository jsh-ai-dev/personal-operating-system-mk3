<script setup lang="ts">
// 백엔드 헬스체크 API 응답 타입 정의
interface HealthResponse {
  status: string
  mongodb: string
  qdrant: string
}

const api = useApi()

// useAsyncData: SSR/CSR 모두 지원하는 Nuxt 데이터 페칭 훅
// 첫 번째 인자 'health'는 캐시 키 — 같은 키로 중복 요청을 방지함
const { data: health, error } = await useAsyncData('health', () =>
  api<HealthResponse>('/api/v1/health'),
)
</script>

<template>
  <main>
    <h1>Personal Operating System mk3</h1>

    <section>
      <h2>Backend Status</h2>
      <!-- 정상 응답 시 각 서비스 상태 표시 -->
      <div v-if="health">
        <p>API <span class="ok">{{ health.status }}</span></p>
        <p>MongoDB <span class="ok">{{ health.mongodb }}</span></p>
        <p>Qdrant <span class="ok">{{ health.qdrant }}</span></p>
      </div>
      <!-- 에러 발생 시 오류 메시지 표시 -->
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
