<!-- [페이지] /quiz — 요약이 있는 대화 목록, 퀴즈 생성/이동 -->
<!-- 요약 기반으로 AI가 4지선다 문제를 생성. 생성된 퀴즈는 DB에 저장해 재사용 -->

<script setup lang="ts">
import type { Conversation } from '~/composables/useChat'

const { listConversations, generateQuiz } = useChat()

const { data: allConversations, refresh } = await useAsyncData('quiz-list', () => listConversations())

// 요약이 있는 대화만 대상
const summarized = computed<Conversation[]>(() =>
  (allConversations.value ?? []).filter(c => c.summary),
)

const openaiModels = [
  { id: 'gpt-5-nano',   label: 'GPT-5 Nano' },
  { id: 'gpt-5-mini',   label: 'GPT-5 Mini' },
  { id: 'gpt-5',        label: 'GPT-5' },
]

// 카드별 모델 선택 상태
const selectedModel = ref<Record<string, string>>({})
const getModel = (id: string) => selectedModel.value[id] ?? 'gpt-5-mini'
const setModel = (id: string, model: string) => { selectedModel.value[id] = model }

const generating = ref<Set<string>>(new Set())
const errors = ref<Record<string, string>>({})

const startGenerate = async (conv: Conversation) => {
  const next = new Set(generating.value)
  next.add(conv.id)
  generating.value = next
  errors.value[conv.id] = ''

  try {
    await generateQuiz(conv.id, getModel(conv.id))
    await refresh()
  } catch (e: any) {
    errors.value[conv.id] = e?.data?.detail ?? '퀴즈 생성 실패'
  } finally {
    const s = new Set(generating.value)
    s.delete(conv.id)
    generating.value = s
  }
}

const providerLabel = (p: string) =>
  ({ openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', gemini: 'Gemini', jetbrains: 'JetBrains' })[p] ?? p

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' })

const formatCost = (v: number | null) => {
  if (v == null) return ''
  return v < 0.0001 ? '<$0.0001' : `$${v.toFixed(4)}`
}
</script>

<template>
  <main>
    <header class="header">
      <h1>AI 퀴즈</h1>
      <div class="nav-links">
        <NuxtLink to="/summaries" class="btn-nav">학습 요약</NuxtLink>
        <NuxtLink to="/chat" class="btn-nav">← 대화 목록</NuxtLink>
      </div>
    </header>

    <div v-if="summarized.length" class="list">
      <div v-for="conv in summarized" :key="conv.id" class="card">
        <div class="card-header">
          <div class="card-meta">
            <span class="badge" :class="conv.provider">{{ providerLabel(conv.provider) }}</span>
            <span class="date">{{ formatDate(conv.updated_at) }}</span>
            <span v-if="conv.quiz" class="badge-quiz">{{ conv.quiz.length }}문제</span>
          </div>
          <div class="card-title-row">
            <span class="card-title">{{ conv.title }}</span>
            <NuxtLink v-if="conv.quiz" :to="`/quiz/${conv.id}`" class="btn-play">퀴즈 풀기 →</NuxtLink>
          </div>
        </div>

        <div class="card-body">
          <div v-if="conv.quiz" class="quiz-info">
            <span class="info-text">생성 모델: {{ conv.quiz_model }}</span>
            <span v-if="conv.quiz_cost_usd" class="info-text cost">{{ formatCost(conv.quiz_cost_usd) }}</span>
          </div>

          <!-- 모델 선택 + 생성/재생성 버튼 -->
          <div class="generate-row">
            <select
              :value="getModel(conv.id)"
              class="model-select"
              @change="setModel(conv.id, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="m in openaiModels" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
            <button
              class="btn-generate"
              :disabled="generating.has(conv.id)"
              @click="startGenerate(conv)"
            >
              {{ generating.has(conv.id) ? '생성 중...' : conv.quiz ? '재생성' : '퀴즈 만들기' }}
            </button>
          </div>
          <p v-if="errors[conv.id]" class="error">{{ errors[conv.id] }}</p>
        </div>
      </div>
    </div>

    <div v-else class="empty">
      <p>요약된 대화가 없습니다.</p>
      <NuxtLink to="/chat">대화 목록에서 요약하기 →</NuxtLink>
    </div>
  </main>
</template>

<style scoped>
main {
  max-width: 760px;
  margin: 40px auto;
  padding: 0 24px;
  font-family: monospace;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}
h1 { font-size: 1.3rem; margin: 0; }
.nav-links { display: flex; gap: 8px; }
.btn-nav {
  font-size: 0.85rem;
  color: #6b7280;
  text-decoration: none;
  padding: 5px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.btn-nav:hover { color: #374151; border-color: #9ca3af; }
.list { display: flex; flex-direction: column; gap: 14px; }
.card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}
.card-header {
  padding: 14px 16px 10px;
  border-bottom: 1px solid #f3f4f6;
  background: #fafafa;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.badge {
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: #f3f4f6;
  color: #374151;
}
.badge.openai { background: #d1fae5; color: #065f46; }
.badge.anthropic { background: #fde68a; color: #78350f; }
.badge.google { background: #dbeafe; color: #1e3a8a; }
.badge.jetbrains { background: #ede9fe; color: #5b21b6; }
.badge-quiz {
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: #e0e7ff;
  color: #3730a3;
}
.date { font-size: 0.75rem; color: #9ca3af; }
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.card-title { font-size: 0.95rem; color: #111; font-weight: 600; flex: 1; }
.btn-play {
  font-size: 0.82rem;
  color: #6366f1;
  text-decoration: none;
  white-space: nowrap;
  font-weight: 600;
}
.btn-play:hover { text-decoration: underline; }
.card-body { padding: 12px 16px; }
.quiz-info {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
}
.info-text {
  font-size: 0.78rem;
  color: #9ca3af;
}
.info-text.cost { color: #6b7280; }
.generate-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.model-select {
  font-family: monospace;
  font-size: 0.82rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 5px 8px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.btn-generate {
  font-family: monospace;
  font-size: 0.82rem;
  padding: 5px 14px;
  border: 1px solid #6366f1;
  border-radius: 6px;
  background: #fff;
  color: #6366f1;
  cursor: pointer;
}
.btn-generate:hover:not(:disabled) { background: #6366f1; color: #fff; }
.btn-generate:disabled { opacity: 0.5; cursor: not-allowed; }
.error { font-size: 0.8rem; color: #ef4444; margin: 6px 0 0; }
.empty {
  text-align: center;
  color: #9ca3af;
  font-size: 0.9rem;
  margin-top: 80px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}
.empty a { color: #6366f1; text-decoration: none; }
.empty a:hover { text-decoration: underline; }
</style>
