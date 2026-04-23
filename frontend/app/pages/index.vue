<!-- [대시보드] 등록된 AI 서비스 목록과 월 구독료 합계를 보여주는 메인 페이지 -->
<!-- AiServiceCard 컴포넌트를 그리드로 나열하고 서비스 추가 버튼을 제공함 -->

<script setup lang="ts">
import type { AIService } from '~/composables/useAiServices'

const { list } = useAiServices()

// 전체 AI 서비스 목록 로드
const { data: services, refresh } = await useAsyncData('ai-services', list)

// USD 서비스 월 구독료 합산 (통화가 다른 경우 단순 합산은 의미 없으므로 USD만)
const totalUSD = computed(() =>
  (services.value ?? [])
    .filter((s: AIService) => s.currency === 'USD')
    .reduce((sum: number, s: AIService) => sum + s.monthly_cost, 0)
)

const totalKRW = computed(() =>
  (services.value ?? [])
    .filter((s: AIService) => s.currency === 'KRW')
    .reduce((sum: number, s: AIService) => sum + s.monthly_cost, 0)
)

// 카드 삭제 후 목록 새로고침
const handleDeleted = async () => {
  await refresh()
}
</script>

<template>
  <main>
    <header class="header">
      <h1>AI 서비스 현황</h1>
      <NuxtLink to="/ai-services/new" class="btn-add">+ 추가</NuxtLink>
    </header>

    <!-- 총 구독료 요약 -->
    <div class="summary">
      <div v-if="totalUSD > 0" class="summary-item">
        <span>USD 합계</span>
        <strong>${{ totalUSD.toFixed(2) }}</strong>
      </div>
      <div v-if="totalKRW > 0" class="summary-item">
        <span>KRW 합계</span>
        <strong>₩{{ totalKRW.toLocaleString() }}</strong>
      </div>
      <span class="count">{{ services?.length ?? 0 }}개 서비스</span>
    </div>

    <!-- 서비스 카드 목록 -->
    <div v-if="services?.length" class="cards">
      <AiServiceCard
        v-for="service in services"
        :key="service.id"
        :service="service"
        @deleted="handleDeleted"
      />
    </div>

    <div v-else class="empty">
      등록된 AI 서비스가 없습니다.
      <NuxtLink to="/ai-services/new">추가하기 →</NuxtLink>
    </div>
  </main>
</template>

<style scoped>
main {
  max-width: 960px;
  margin: 40px auto;
  padding: 0 24px;
  font-family: monospace;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
h1 { font-size: 1.3rem; }
.btn-add {
  padding: 6px 14px;
  border: 1px solid #6366f1;
  border-radius: 6px;
  color: #6366f1;
  text-decoration: none;
  font-size: 0.85rem;
  font-family: monospace;
}
.btn-add:hover { background: #eef2ff; }
.summary {
  display: flex;
  align-items: baseline;
  gap: 20px;
  margin-bottom: 28px;
  font-size: 0.85rem;
  color: #666;
}
.summary-item { display: flex; align-items: baseline; gap: 8px; }
.summary-item strong { font-size: 1.4rem; color: #111; }
.count { color: #aaa; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.empty { color: #aaa; font-size: 0.9rem; margin-top: 60px; text-align: center; }
.empty a { color: #6366f1; text-decoration: none; margin-left: 4px; }
</style>
