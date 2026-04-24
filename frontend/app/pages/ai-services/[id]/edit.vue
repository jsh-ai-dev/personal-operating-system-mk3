<!-- [수정 폼] 기존 AI 서비스 구독 정보를 불러와 수정할 수 있는 페이지 -->
<!-- URL의 id 파라미터로 대상 서비스를 특정하고, 기존 데이터를 폼에 채워서 보여줌 -->

<script setup lang="ts">
import type { AIServiceForm } from '~/composables/useAiServices'

const route = useRoute()
const { get, update } = useAiServices()
const router = useRouter()

const id = route.params.id as string
const error = ref('')

// 기존 서비스 데이터 로드
const { data: service } = await useAsyncData(`ai-service-${id}`, () => get(id))

if (!service.value) {
  throw createError({ statusCode: 404, statusMessage: 'AI service not found' })
}

// 기존 데이터를 초기값으로 세팅 (null은 빈 문자열로 변환해 input에 표시)
const form = reactive({
  name: service.value.name,
  plan_name: service.value.plan_name ?? '',
  monthly_cost: (service.value.monthly_cost ?? '') as number | string,
  currency: service.value.currency,
  billing_day: (service.value.billing_day ?? '') as number | string,
  usage_limit: (service.value.usage_limit ?? '') as number | string,
  usage_current: (service.value.usage_current ?? '') as number | string,
  usage_unit: service.value.usage_unit ?? '',
  billing_url: service.value.billing_url ?? '',
  notes: service.value.notes ?? '',
})

const toNum = (v: number | string): number | null =>
  v !== '' ? Number(v) : null

const toStr = (v: string): string | null =>
  v.trim() !== '' ? v.trim() : null

const submit = async () => {
  error.value = ''
  try {
    const data: AIServiceForm = {
      name: form.name,
      plan_name: toStr(form.plan_name),
      monthly_cost: toNum(form.monthly_cost),
      currency: form.currency,
      billing_day: toNum(form.billing_day),
      usage_limit: toNum(form.usage_limit),
      usage_current: toNum(form.usage_current),
      usage_unit: toStr(form.usage_unit),
      billing_url: toStr(form.billing_url),
      notes: toStr(form.notes),
    }
    await update(id, data)
    router.push('/')
  } catch (e: any) {
    error.value = e.message ?? '저장 중 오류가 발생했습니다.'
  }
}
</script>

<template>
  <main>
    <header class="header">
      <NuxtLink to="/" class="back">← 목록으로</NuxtLink>
      <h1>{{ service?.name }} 수정</h1>
    </header>

    <form class="form" @submit.prevent="submit">
      <div class="field">
        <label>서비스명</label>
        <input v-model="form.name" type="text" required />
      </div>

      <div class="field">
        <label>플랜명</label>
        <input v-model="form.plan_name" type="text" placeholder="스크래핑으로 자동 입력" />
      </div>

      <div class="row">
        <div class="field">
          <label>월 구독료</label>
          <input v-model="form.monthly_cost" type="number" min="0" step="0.01" />
        </div>
        <div class="field">
          <label>통화</label>
          <select v-model="form.currency">
            <option value="USD">USD ($)</option>
            <option value="KRW">KRW (₩)</option>
          </select>
        </div>
      </div>

      <div class="field">
        <label>결제일 (매월 몇 일)</label>
        <input v-model="form.billing_day" type="number" min="1" max="31" />
      </div>

      <div class="section-label">사용량 (선택)</div>

      <div class="row">
        <div class="field">
          <label>사용 한도</label>
          <input v-model="form.usage_limit" type="number" min="0" />
        </div>
        <div class="field">
          <label>현재 사용량</label>
          <input v-model="form.usage_current" type="number" min="0" />
        </div>
      </div>

      <div class="field">
        <label>단위</label>
        <input v-model="form.usage_unit" type="text" placeholder="예: messages / 3h" />
      </div>

      <div class="field">
        <label>청구 페이지 URL (선택)</label>
        <input v-model="form.billing_url" type="url" />
      </div>

      <div class="field">
        <label>메모 (선택)</label>
        <textarea v-model="form.notes" rows="2" />
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="actions">
        <NuxtLink to="/" class="btn-cancel">취소</NuxtLink>
        <button type="submit" class="btn-submit">저장</button>
      </div>
    </form>
  </main>
</template>

<style scoped>
main { max-width: 520px; margin: 40px auto; padding: 0 24px; font-family: monospace; }
.header { margin-bottom: 24px; }
.back { font-size: 0.85rem; color: #888; text-decoration: none; }
.back:hover { color: #333; }
h1 { font-size: 1.2rem; margin-top: 8px; }
.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 6px; }
label { font-size: 0.8rem; color: #555; }
input, select, textarea {
  font-family: monospace;
  font-size: 0.9rem;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  outline: none;
  background: white;
}
input:focus, select:focus, textarea:focus { border-color: #6366f1; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.section-label { font-size: 0.78rem; color: #aaa; border-bottom: 1px solid #f3f4f6; padding-bottom: 6px; }
.error { color: #ef4444; font-size: 0.85rem; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }
.btn-cancel {
  font-family: monospace;
  font-size: 0.85rem;
  padding: 8px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  text-decoration: none;
  color: #555;
}
.btn-submit {
  font-family: monospace;
  font-size: 0.85rem;
  padding: 8px 16px;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.btn-submit:hover { background: #4f46e5; }
</style>
