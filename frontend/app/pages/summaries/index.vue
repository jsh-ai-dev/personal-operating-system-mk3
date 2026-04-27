<!-- [페이지] /summaries — 요약이 생성된 대화들을 모아보는 학습 복습 페이지 -->
<!-- 대화 상세 페이지에서 '요약하기'로 생성한 요약을 카드 형태로 나열 -->

<script setup lang="ts">
import type { Conversation } from '~/composables/useChat'

const { listConversations } = useChat()

const { data: allConversations } = await useAsyncData('summaries', () => listConversations())

// 요약이 있는 대화만 필터링 — updated_at 내림차순 (이미 정렬되어 있음)
const summarized = computed<Conversation[]>(() =>
  (allConversations.value ?? []).filter(c => c.summary),
)

const selectedProvider = ref<string>('all')
const providers = computed(() => {
  const set = new Set(summarized.value.map(c => c.provider))
  return ['all', ...set]
})

const filtered = computed(() =>
  selectedProvider.value === 'all'
    ? summarized.value
    : summarized.value.filter(c => c.provider === selectedProvider.value),
)

const expandedIds = ref<Set<string>>(new Set())
const toggleExpand = (id: string) => {
  const next = new Set(expandedIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedIds.value = next
}

const providerLabel = (p: string) =>
  ({ openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', gemini: 'Gemini', jetbrains: 'JetBrains' })[p] ?? p

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' })

// 마크다운 → HTML 변환 (외부 라이브러리 없이 요약 형식에 맞게 처리)
const renderSummary = (text: string): string => {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^---$/gm, '<hr>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}
</script>

<template>
  <main>
    <header class="header">
      <h1>학습 요약</h1>
      <div class="header-actions">
        <select v-model="selectedProvider" class="filter-select">
          <option v-for="p in providers" :key="p" :value="p">
            {{ p === 'all' ? '전체' : providerLabel(p) }}
          </option>
        </select>
        <NuxtLink to="/quiz" class="btn-go-chat">AI 퀴즈</NuxtLink>
        <NuxtLink to="/chat" class="btn-go-chat">← 대화 목록</NuxtLink>
      </div>
    </header>

    <div v-if="filtered.length" class="list">
      <div v-for="conv in filtered" :key="conv.id" class="card">
        <div class="card-header">
          <div class="card-meta">
            <span class="badge" :class="conv.provider">{{ providerLabel(conv.provider) }}</span>
            <span class="date">{{ formatDate(conv.updated_at) }}</span>
          </div>
          <div class="card-title-row">
            <span class="card-title">{{ conv.title }}</span>
            <NuxtLink :to="`/chat/${conv.id}`" class="btn-view-conv">대화 보기 →</NuxtLink>
          </div>
        </div>

        <div class="card-body">
          <!-- 요약 미리보기: 항상 보이는 첫 부분 + 접기/펼치기 -->
          <div
            class="summary-content"
            :class="{ expanded: expandedIds.has(conv.id) }"
            v-html="renderSummary(conv.summary!)"
          />
          <button class="btn-expand" @click="toggleExpand(conv.id)">
            {{ expandedIds.has(conv.id) ? '▲ 접기' : '▼ 더 보기' }}
          </button>
        </div>
      </div>
    </div>

    <div v-else class="empty">
      <p>아직 요약된 대화가 없습니다.</p>
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
.header-actions { display: flex; align-items: center; gap: 10px; }
.filter-select {
  font-family: monospace;
  font-size: 0.85rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 5px 10px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.btn-go-chat {
  font-size: 0.85rem;
  color: #6b7280;
  text-decoration: none;
  padding: 5px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.btn-go-chat:hover { color: #374151; border-color: #9ca3af; }
.list { display: flex; flex-direction: column; gap: 16px; }
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
  gap: 10px;
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
.date { font-size: 0.75rem; color: #9ca3af; }
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.card-title { font-size: 0.95rem; color: #111; font-weight: 600; flex: 1; }
.btn-view-conv {
  font-size: 0.78rem;
  color: #6366f1;
  text-decoration: none;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-view-conv:hover { text-decoration: underline; }
.card-body { padding: 14px 16px 10px; }
.summary-content {
  font-size: 0.85rem;
  line-height: 1.75;
  color: #1f2937;
  /* 기본 상태: 최대 12줄만 표시 */
  max-height: calc(1.75em * 12);
  overflow: hidden;
  mask-image: linear-gradient(to bottom, black 70%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, black 70%, transparent 100%);
  transition: max-height 0.3s ease;
}
.summary-content.expanded {
  max-height: none;
  mask-image: none;
  -webkit-mask-image: none;
}
/* 요약 마크다운 스타일 */
.summary-content :deep(h2) { font-size: 1rem; font-weight: 700; margin-bottom: 8px; color: #111; }
.summary-content :deep(h3) { font-size: 0.88rem; font-weight: 600; margin: 14px 0 4px; color: #374151; }
.summary-content :deep(hr) { border: none; border-top: 1px solid #e5e7eb; margin: 10px 0; }
.summary-content :deep(strong) { color: #111; }
.summary-content :deep(em) { color: #9ca3af; font-style: normal; font-size: 0.78rem; }
.btn-expand {
  margin-top: 8px;
  background: none;
  border: none;
  font-family: monospace;
  font-size: 0.78rem;
  color: #6366f1;
  cursor: pointer;
  padding: 0;
}
.btn-expand:hover { text-decoration: underline; }
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
