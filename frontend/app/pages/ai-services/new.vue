<!-- [추가 폼] 새 AI 서비스 구독 정보를 입력해 저장하는 페이지 -->
<!-- 서비스명 드롭다운(사전 정의 목록), 플랜, 구독료, 결제일, 사용량 등을 입력함 -->

<script setup lang="ts">
import type { AIServiceForm } from '~/composables/useAiServices'

const { create } = useAiServices()
const router = useRouter()

// 사전 정의된 AI 서비스 이름 목록
const SERVICE_NAMES = [
  'ChatGPT', 'Codex', 'Gemini', 'Gemini Code Assist',
  'Claude', 'Claude Code', 'Copilot', 'Cursor', '직접 입력',
]

const selectedName = ref('ChatGPT')
const customName = ref('')
const error = ref('')

const form = reactive({
  name: 'ChatGPT',
  plan_name: '',
  monthly_cost: '' as number | string,
  currency: 'USD',
  billing_day: '' as number | string,
  usage_limit: '' as number | string,
  usage_current: '' as number | string,
  usage_unit: '',
  billing_url: '',
  notes: '',
})

// 드롭다운 선택 변경 시 form.name 동기화
watch(selectedName, (val) => {
  if (val !== '직접 입력') form.name = val
})

watch(customName, (val) => {
  if (selectedName.value === '직접 입력') form.name = val
})

// 빈 문자열을 null로, 숫자 문자열을 number로 변환하는 헬퍼
const toNum = (v: number | string): number | null =>
  v !== '' ? Number(v) : null

const toStr = (v: string): string | null =>
  v.trim() !== '' ? v.trim() : null

const submit = async () => {
  error.value = ''
  try {
    const data: AIServiceForm = {
      name: form.name,
      plan_name: form.plan_name,
      monthly_cost: Number(form.monthly_cost),
      currency: form.currency,
      billing_day: Number(form.billing_day),
      usage_limit: toNum(form.usage_limit),
      usage_current: toNum(form.usage_current),
      usage_unit: toStr(form.usage_unit),
      billing_url: toStr(form.billing_url),
      notes: toStr(form.notes),
    }
    await create(data)
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
      <h1>AI 서비스 추가</h1>
    </header>

    <form class="form" @submit.prevent="submit">
      <div class="field">
        <label>서비스명</label>
        <select v-model="selectedName">
          <option v-for="n in SERVICE_NAMES" :key="n">{{ n }}</option>
        </select>
        <input
          v-if="selectedName === '직접 입력'"
          v-model="customName"
          type="text"
          placeholder="서비스명 입력"
          required
        />
      </div>

      <div class="field">
        <label>플랜명</label>
        <input v-model="form.plan_name" type="text" placeholder="예: Plus, Pro, Max" required />
      </div>

      <div class="row">
        <div class="field">
          <label>월 구독료</label>
          <input v-model="form.monthly_cost" type="number" min="0" step="0.01" placeholder="예: 20" required />
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
        <input v-model="form.billing_day" type="number" min="1" max="31" placeholder="예: 15" required />
      </div>

      <div class="section-label">사용량 (선택)</div>

      <div class="row">
        <div class="field">
          <label>사용 한도</label>
          <input v-model="form.usage_limit" type="number" min="0" placeholder="예: 40" />
        </div>
        <div class="field">
          <label>현재 사용량</label>
          <input v-model="form.usage_current" type="number" min="0" placeholder="예: 12" />
        </div>
      </div>

      <div class="field">
        <label>단위</label>
        <input v-model="form.usage_unit" type="text" placeholder="예: messages / 3h, requests / month" />
      </div>

      <div class="field">
        <label>청구 페이지 URL (선택)</label>
        <input v-model="form.billing_url" type="url" placeholder="https://..." />
      </div>

      <div class="field">
        <label>메모 (선택)</label>
        <textarea v-model="form.notes" rows="2" placeholder="참고 사항" />
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
