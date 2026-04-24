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

// 다음 결제일 계산: 이번 달 결제일이 이미 지났으면 다음 달로 (billing_day가 없으면 null)
const nextBilling = computed(() => {
  const day = props.service.billing_day
  if (!day) return null
  const today = new Date()
  let date = new Date(today.getFullYear(), today.getMonth(), day)
  if (date <= today) {
    date = new Date(today.getFullYear(), today.getMonth() + 1, day)
  }
  return date.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })
})

// 사용량 퍼센트 (한도와 현재 사용량 모두 있을 때만 계산)
const usagePct = computed(() => {
  const { usage_limit, usage_current } = props.service
  if (!usage_limit || usage_current === null || usage_current === undefined) return null
  return Math.min(Math.round((usage_current / usage_limit) * 100), 100)
})

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

    <!-- 다음 결제일 -->
    <div class="billing">
      <template v-if="nextBilling">다음 결제일 <span class="date">{{ nextBilling }}</span></template>
      <template v-else><span style="color:#ccc">결제일 미입력</span></template>
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
          {{ service.usage_current?.toLocaleString() }} / {{ service.usage_limit.toLocaleString() }}
        </span>
        <span v-else>한도 {{ service.usage_limit.toLocaleString() }}</span>
        <span v-if="service.usage_unit" class="unit"> {{ service.usage_unit }}</span>
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
