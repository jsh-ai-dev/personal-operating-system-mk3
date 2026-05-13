<!-- [카드 컴포넌트] AI 서비스 한 개의 구독 정보를 카드 형태로 표시하는 컴포넌트 -->
<!-- 구독료, 다음 결제일, 사용량 진행바, 청구 페이지 링크, 수정/삭제 버튼을 포함 -->

<script setup lang="ts">
import type { AIService } from '~/composables/useAiServices'

const props = defineProps<{
  service: AIService
  syncStatus?: 'idle' | 'syncing' | 'done' | 'login_required' | 'error'
}>()
const emit = defineEmits<{ deleted: [id: string]; sync: [] }>()

const { remove } = useAiServices()

// 구독일: subscribed_at ISO 문자열을 한국어 날짜로 변환
const subscribedAt = computed(() => {
  const raw = props.service.subscribed_at
  if (!raw) return null
  const d = new Date(raw)
  return isNaN(d.getTime()) ? null : d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })
})

// usage_current가 1이면 스크래퍼 호출 자체로 인한 noise로 간주 → 0으로 표시
const isEffectivelyZero = computed(() => props.service.usage_current === 1)

const usagePct = computed(() => {
  const { usage_limit, usage_current } = props.service
  if (!usage_limit || usage_current === null || usage_current === undefined) return null
  if (isEffectivelyZero.value) return 0
  return Math.min(Math.round((usage_current / usage_limit) * 1000) / 10, 100)
})

// 0으로 간주할 때는 리셋 시간 제거 — 매 스크래핑마다 바뀌는 의미없는 시간이기 때문
const displayCurrent = computed(() => isEffectivelyZero.value ? 0 : props.service.usage_current)
const displayUnit = computed(() =>
  isEffectivelyZero.value ? '%' : (props.service.usage_unit ?? null)
)

// 사용량 비율에 따른 색상: 90% 이상 빨강, 70% 이상 노랑, 그 이하 초록
const usageColor = computed(() => {
  if (usagePct.value === null) return '#22c55e'
  if (usagePct.value >= 90) return '#ef4444'
  if (usagePct.value >= 70) return '#f59e0b'
  return '#22c55e'
})

const currencySymbol = computed(() =>
  props.service.currency === 'KRW' ? '₩' : '$'
)

const handleDelete = async () => {
  if (!confirm(`${props.service.name}을(를) 삭제하시겠습니까?`)) return
  await remove(props.service.id)
  emit('deleted', props.service.id)
}
</script>

<template>
  <div class="card">
    <!-- 서비스명 + 월 구독료 -->
    <div class="card-header">
      <div>
        <div class="name">{{ service.name }}</div>
        <div class="plan">{{ service.plan_name }}</div>
      </div>
      <div class="cost">
        <template v-if="service.monthly_cost != null">
          {{ currencySymbol }}{{ service.monthly_cost.toLocaleString() }}<span class="per-month">/월</span>
        </template>
        <template v-else><span class="per-month">미입력</span></template>
      </div>
    </div>

    <!-- 구독일 -->
    <div class="billing">
      <template v-if="subscribedAt">구독일 <span class="date">{{ subscribedAt }}</span></template>
      <template v-else><span style="color:#ccc">구독일 미입력</span></template>
    </div>

    <!-- 사용량 바: usage_limit이 설정된 경우에만 표시 -->
    <div v-if="service.usage_limit" class="usage">
      <div class="usage-header">
        <span>사용량</span>
        <span v-if="usagePct !== null" :style="{ color: usageColor }">{{ usagePct }}%</span>
      </div>
      <div class="bar-bg">
        <div
          v-if="usagePct !== null"
          class="bar-fill"
          :style="{ width: usagePct + '%', backgroundColor: usageColor }"
        />
      </div>
      <div class="usage-detail">
        <span v-if="usagePct !== null">
          {{ displayCurrent?.toLocaleString() }} / {{ service.usage_limit.toLocaleString() }}
        </span>
        <span v-else>한도 {{ service.usage_limit.toLocaleString() }}</span>
        <span v-if="displayUnit" class="unit"> {{ displayUnit }}</span>
      </div>
    </div>

    <!-- 청구 페이지 링크 + 갱신/수정/삭제 버튼 -->
    <div class="actions">
      <a v-if="service.billing_url" :href="service.billing_url" target="_blank" class="link">청구 페이지 →</a>
      <span v-else class="link-empty">-</span>
      <div class="btns">
        <button
          v-if="syncStatus !== undefined"
          class="btn btn-sync"
          :disabled="syncStatus === 'syncing'"
          @click="emit('sync')"
        >
          <span v-if="syncStatus === 'syncing'">갱신 중...</span>
          <span v-else-if="syncStatus === 'done'">✓ 갱신됨</span>
          <span v-else-if="syncStatus === 'login_required'">로그인 필요</span>
          <span v-else-if="syncStatus === 'error'">갱신 실패</span>
          <span v-else>갱신</span>
        </button>
        <NuxtLink :to="`/ai-services/${service.id}/edit`" class="btn">수정</NuxtLink>
        <button class="btn btn-delete" @click="handleDelete">삭제</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  font-family: monospace;
}
.card-header { display: flex; justify-content: space-between; align-items: flex-start; }
.name { font-size: 1rem; font-weight: bold; }
.plan { font-size: 0.8rem; color: #888; margin-top: 2px; }
.cost { font-size: 1.1rem; font-weight: bold; }
.per-month { font-size: 0.75rem; color: #888; }
.billing { font-size: 0.8rem; color: #666; }
.date { color: #111; font-weight: bold; }
.usage { display: flex; flex-direction: column; gap: 4px; }
.usage-header { display: flex; justify-content: space-between; font-size: 0.8rem; }
.bar-bg { background: #f3f4f6; border-radius: 4px; height: 6px; }
.bar-fill { height: 6px; border-radius: 4px; transition: width 0.3s; }
.usage-detail { font-size: 0.75rem; color: #888; }
.unit { color: #aaa; }
.actions { display: flex; justify-content: space-between; align-items: center; margin-top: 4px; }
.link { font-size: 0.8rem; color: #6366f1; text-decoration: none; }
.link:hover { text-decoration: underline; }
.link-empty { font-size: 0.8rem; color: #ccc; }
.btns { display: flex; gap: 8px; }
.btn {
  font-size: 0.75rem;
  font-family: monospace;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  background: white;
  text-decoration: none;
  color: #374151;
}
.btn:hover { background: #f9fafb; }
.btn-delete { color: #ef4444; border-color: #fca5a5; }
.btn-delete:hover { background: #fef2f2; }
.btn-sync { color: #6366f1; border-color: #c7d2fe; }
.btn-sync:hover:not(:disabled) { background: #eef2ff; }
.btn-sync:disabled { opacity: 0.5; cursor: default; }
</style>
