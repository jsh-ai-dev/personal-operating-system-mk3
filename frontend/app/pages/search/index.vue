<!-- [페이지] /search — 의미 기반 대화 검색 페이지 -->
<!-- 질의어를 입력하면 OpenAI 임베딩 + Qdrant 유사도 검색으로 관련 대화를 찾아줌 -->
<!-- 키워드가 없어도 의미가 비슷한 대화를 찾아내는 것이 일반 텍스트 검색과의 차이점 -->

<script setup lang="ts">
import type { IndexResponse, SearchResult } from '~/composables/useSearch'

const { search, indexAll } = useSearch()

const query = ref('')
const results = ref<SearchResult[]>([])
const searchCost = ref<number | null>(null)
const isSearching = ref(false)
const isIndexing = ref(false)
const indexResult = ref<IndexResponse | null>(null)
const error = ref<string | null>(null)
const hasSearched = ref(false)

const handleSearch = async () => {
  const q = query.value.trim()
  if (!q || isSearching.value) return

  error.value = null
  searchCost.value = null
  isSearching.value = true
  hasSearched.value = true
  try {
    const res = await search(q)
    results.value = res.results
    searchCost.value = res.cost_usd
  } catch (e: any) {
    error.value = e?.data?.detail ?? '검색 중 오류가 발생했습니다'
    results.value = []
  } finally {
    isSearching.value = false
  }
}

// isComposing: 한글 IME 조합 중 엔터를 검색으로 오해하지 않도록
// (조합 중 엔터는 글자 확정용이지 검색 의도가 아님)
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.isComposing) {
    e.preventDefault()
    handleSearch()
  }
}

const handleIndexAll = async () => {
  isIndexing.value = true
  indexResult.value = null
  try {
    indexResult.value = await indexAll()
  } catch (e: any) {
    error.value = e?.data?.detail ?? '인덱싱 중 오류가 발생했습니다'
  } finally {
    isIndexing.value = false
  }
}

// window.open 사용 이유: <a target="_blank">는 Nuxt가 첫 클릭을 라우터로 가로채는 경우가 있음
// 클릭 이벤트 핸들러에서 동기적으로 호출하면 팝업 차단도 우회됨
const openConversation = (id: string) => {
  window.open(`/chat/${id}`, '_blank', 'noopener,noreferrer')
}

// 모델명으로 뱃지 색상 구분 — provider 필드 없이 model 값만 payload에 저장하므로 model로 판별
const badgeClass = (model: string) => {
  if (model.startsWith('gpt') || model.startsWith('o1') || model.startsWith('o3')) return 'openai'
  if (model.startsWith('claude')) return 'anthropic'
  if (model.startsWith('gemini')) return 'google'
  if (model === 'codex') return 'jetbrains'
  return 'default'
}

const badgeLabel = (model: string) => {
  if (model === 'claude-code') return 'Claude Code'
  if (model === 'claude') return 'Claude (임포트)'
  if (model === 'codex') return 'Codex'
  if (model === 'gemini') return 'Gemini (임포트)'
  return model
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' })

// score는 코사인 유사도(0~1) — 100 곱해 %로 표시
const scorePercent = (score: number) => `${Math.round(score * 100)}%`

const scoreColor = (score: number) => {
  if (score >= 0.8) return '#22c55e'
  if (score >= 0.6) return '#f59e0b'
  return '#9ca3af'
}
</script>

<template>
  <main>
    <header class="header">
      <h1>의미 검색</h1>
      <div class="header-actions">
        <NuxtLink to="/chat" class="btn-link">← 대화 목록</NuxtLink>
      </div>
    </header>

    <div class="search-box">
      <input
        v-model="query"
        type="text"
        class="search-input"
        autocomplete="off"
        placeholder="예: React 훅 최적화, Docker 네트워크 설정, FastAPI 의존성 주입..."
        @keydown="handleKeydown"
      />
      <button class="btn-search" :disabled="isSearching || !query.trim()" @click="handleSearch">
        {{ isSearching ? '···' : '검색' }}
      </button>
    </div>

    <div v-show="error" class="error-msg">{{ error }}</div>

    <!-- 인덱싱 버튼 — 최초 1회 또는 임베딩 누락 시 사용 -->
    <div class="index-section">
      <button class="btn-index" :disabled="isIndexing" @click="handleIndexAll">
        {{ isIndexing ? '인덱싱 중...' : '전체 대화 인덱싱' }}
      </button>
      <span class="index-hint">처음 사용 시 또는 검색이 안 될 때 클릭하세요</span>
      <span v-show="indexResult" class="index-result">
        {{ indexResult?.indexed }}건 인덱싱 / {{ indexResult?.skipped }}건 스킵 / {{ indexResult?.total }}건 전체
        · ${{ indexResult?.cost_usd.toFixed(6) }}
        <span v-show="(indexResult?.failed ?? 0) > 0" class="failed-count">
          ({{ indexResult?.failed }}건 실패)
        </span>
      </span>
    </div>

    <!-- 검색 결과 -->
    <div v-show="hasSearched && !isSearching" class="results-section">
      <div v-show="searchCost !== null" class="search-cost">
        검색 비용: ${{ searchCost?.toFixed(6) }}
      </div>
      <div v-show="results.length > 0" class="results-list">
        <div v-for="r in results" :key="r.conversation_id" class="result-card">
          <div class="result-meta">
            <span class="badge" :class="badgeClass(r.model)">{{ badgeLabel(r.model) }}</span>
            <span class="date">{{ formatDate(r.created_at) }}</span>
            <span class="score" :style="{ color: scoreColor(r.score) }">
              유사도 {{ scorePercent(r.score) }}
            </span>
          </div>
          <div class="result-title-row">
            <span class="result-title">{{ r.title }}</span>
            <button class="btn-view" @click="openConversation(r.conversation_id)">대화 보기 →</button>
          </div>
        </div>
      </div>

      <div v-show="results.length === 0" class="empty">
        <p>관련 대화를 찾지 못했습니다.</p>
        <p class="empty-hint">아직 인덱싱이 안 됐다면 위의 "전체 대화 인덱싱"을 먼저 실행해보세요.</p>
      </div>
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
  margin-bottom: 24px;
}
h1 { font-size: 1.3rem; margin: 0; }
.header-actions { display: flex; gap: 8px; }
.btn-link {
  font-size: 0.85rem;
  color: #6b7280;
  text-decoration: none;
  padding: 5px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.btn-link:hover { color: #374151; border-color: #9ca3af; }
.search-box {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.search-input {
  flex: 1;
  padding: 12px 16px;
  font-family: monospace;
  font-size: 0.9rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  outline: none;
  box-sizing: border-box;
  color: #111;
}
.search-input:focus { border-color: #6366f1; box-shadow: 0 0 0 2px #eef2ff; }
.search-input::placeholder { color: #9ca3af; }
.btn-search {
  padding: 0 20px;
  background: #6366f1;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-family: monospace;
  font-size: 0.9rem;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-search:hover:not(:disabled) { background: #4f46e5; }
.btn-search:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg {
  font-size: 0.83rem;
  color: #ef4444;
  margin-bottom: 12px;
}
.index-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
  flex-wrap: wrap;
}
.btn-index {
  font-family: monospace;
  font-size: 0.8rem;
  padding: 5px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.btn-index:hover:not(:disabled) { border-color: #6366f1; color: #6366f1; }
.btn-index:disabled { opacity: 0.5; cursor: not-allowed; }
.index-hint { font-size: 0.78rem; color: #9ca3af; }
.index-result { font-size: 0.78rem; color: #22c55e; }
.failed-count { color: #f59e0b; }
.results-section { margin-top: 4px; }
.search-cost { font-size: 0.75rem; color: #9ca3af; margin-bottom: 12px; }
.results-list { display: flex; flex-direction: column; gap: 10px; }
.result-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 16px;
  transition: border-color 0.15s;
}
.result-card:hover { border-color: #6366f1; }
.result-meta {
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
.score { font-size: 0.75rem; font-weight: 600; margin-left: auto; }
.result-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.result-title { font-size: 0.92rem; color: #111; font-weight: 500; flex: 1; }
.btn-view {
  font-size: 0.78rem;
  font-family: monospace;
  color: #6366f1;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
.btn-view:hover { text-decoration: underline; }
.empty {
  text-align: center;
  color: #9ca3af;
  font-size: 0.88rem;
  margin-top: 40px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: center;
}
.empty-hint { font-size: 0.8rem; }
</style>
