<!-- [페이지] /news/:id — 기사 상세 + AI 분석 -->
<!-- 본문 전체 표시, 분석 버튼 클릭 시 하이라이트 HTML·키워드·지원동기·현직자 질문 표시 -->

<script setup lang="ts">
import type { Article } from '~/composables/useNews'

import type { NewsModel } from '~/composables/useNews'

const route = useRoute()
const { get, getModels, analyze } = useNews()

const id = route.params.id as string

const { data: article } = await useAsyncData(`news-${id}`, () => get(id))

const models = ref<NewsModel[]>([])
const selectedModel = ref('gpt-5-mini')
const analyzing = ref(false)
const error = ref('')

onMounted(async () => {
  try {
    models.value = await getModels()
  } catch (_) {}
})

const onAnalyze = async () => {
  analyzing.value = true
  error.value = ''
  try {
    const updated = await analyze(id, selectedModel.value)
    article.value = updated
  } catch (e: any) {
    error.value = e.data?.detail ?? '분석 중 오류가 발생했습니다.'
  } finally {
    analyzing.value = false
  }
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' })

const formatCost = (cost: number) => {
  if (cost === 0) return '$0'
  if (cost < 0.0001) return '<$0.0001'
  return `$${cost.toFixed(4)}`
}

const modelLabel = (m: NewsModel) => `${m.id} ($${m.input_per_1m}/$${m.output_per_1m})`
</script>

<template>
  <main v-if="article">
    <nav class="breadcrumb">
      <NuxtLink :to="route.query.date ? `/news?date=${route.query.date}` : '/news'">← 목록</NuxtLink>
      <span>{{ article.page_num }}면</span>
    </nav>

    <!-- 기사 헤더 -->
    <header class="article-header">
      <div class="article-meta">
        <span class="page-badge">{{ article.page_num }}면</span>
        <span class="date-text">{{ article.date }}</span>
      </div>
      <h1 class="article-title">{{ article.title }}</h1>
      <div class="tag-row">
        <span v-for="c in article.companies" :key="c" class="tag company">{{ c }}</span>
        <span v-for="t in article.tags" :key="t" class="tag topic">{{ t }}</span>
      </div>
      <a :href="article.url" target="_blank" class="source-link">원문 보기 →</a>
    </header>

    <!-- 기사 본문 -->
    <section class="content-section">
      <p class="content">{{ article.content }}</p>
    </section>

    <!-- AI 분석 영역 -->
    <section class="analysis-section">
      <div class="analysis-header">
        <h2>AI 분석</h2>
        <div class="analysis-controls">
          <select v-model="selectedModel" class="model-select" :disabled="analyzing">
            <option v-for="m in models" :key="m.id" :value="m.id">{{ modelLabel(m) }}</option>
          </select>
          <button
            v-if="!article.analysis"
            class="btn-analyze"
            :disabled="analyzing"
            @click="onAnalyze"
          >
            {{ analyzing ? '분석 중…' : '분석하기' }}
          </button>
          <button
            v-else
            class="btn-reanalyze"
            :disabled="analyzing"
            @click="onAnalyze"
          >
            {{ analyzing ? '분석 중…' : '재분석' }}
          </button>
        </div>
        <span v-if="article.analysis?.analysis_model" class="analysis-cost-info">
          {{ article.analysis.analysis_model }} · {{ formatCost(article.analysis.analysis_cost_usd) }}
        </span>
      </div>

      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="analyzing" class="analyzing-placeholder">
        AI가 기사를 분석하고 있습니다…
      </div>

      <div v-else-if="article.analysis" class="analysis-body">

        <!-- 1. 하이라이트 본문 -->
        <div class="analysis-block">
          <h3>본문 하이라이트</h3>
          <p class="legend">
            <span class="num-sample">빨간 문장</span> 숫자·수치 포함 &nbsp;
            <span class="kw-sample">파란 문장</span> 키워드 포함
          </p>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div class="highlighted" v-html="article.analysis.highlighted_html" />
        </div>

        <!-- 2. 개발자 키워드 -->
        <div class="analysis-block">
          <h3>개발자 키워드</h3>
          <div class="keyword-list">
            <div
              v-for="kw in article.analysis.keywords"
              :key="kw.keyword"
              class="keyword-item"
            >
              <span class="kw-label">{{ kw.keyword }}</span>
              <span class="kw-desc">{{ kw.explanation }}</span>
            </div>
          </div>
        </div>

        <!-- 3. 지원 동기 요약 -->
        <div class="analysis-block">
          <h3>지원 동기 활용 포인트</h3>
          <p class="motivation">{{ article.analysis.motivation_summary }}</p>
        </div>

        <!-- 4. 현직자 질문 -->
        <div class="analysis-block">
          <h3>현직자 질문</h3>
          <ol class="question-list">
            <li v-for="(q, i) in article.analysis.questions" :key="i">
              <p class="q-text">{{ q.question }}</p>
              <p class="q-answer">{{ q.expected_answer }}</p>
            </li>
          </ol>
        </div>

        <p class="analyzed-at">분석일시: {{ formatDate(article.analysis.analyzed_at) }}</p>
      </div>

      <div v-else class="empty-analysis">
        버튼을 눌러 AI 분석을 시작하세요.
      </div>
    </section>
  </main>

  <main v-else class="not-found">
    기사를 찾을 수 없습니다. <NuxtLink to="/news">목록으로</NuxtLink>
  </main>
</template>

<style scoped>
main {
  max-width: 780px;
  margin: 40px auto;
  padding: 0 24px;
  font-family: monospace;
}
.not-found {
  text-align: center;
  margin-top: 80px;
  color: #9ca3af;
}
.not-found a { color: #6366f1; text-decoration: none; }
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.82rem;
  color: #9ca3af;
  margin-bottom: 20px;
}
.breadcrumb a { color: #6366f1; text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.article-header { margin-bottom: 24px; }
.article-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.page-badge {
  font-size: 0.72rem;
  background: #ede9fe;
  color: #5b21b6;
  border-radius: 4px;
  padding: 2px 7px;
  font-weight: 600;
}
.date-text { font-size: 0.78rem; color: #9ca3af; }
.article-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #111;
  line-height: 1.5;
  margin: 0 0 10px;
}
.tag-row { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
.tag {
  font-size: 0.72rem;
  border-radius: 4px;
  padding: 2px 7px;
}
.tag.company { background: #dbeafe; color: #1e40af; }
.tag.topic   { background: #f3f4f6; color: #374151; }
.source-link { font-size: 0.8rem; color: #6366f1; text-decoration: none; }
.source-link:hover { text-decoration: underline; }
.content-section {
  border-top: 1px solid #e5e7eb;
  padding: 20px 0;
  margin-bottom: 32px;
}
.content {
  font-size: 0.88rem;
  line-height: 1.9;
  color: #1f2937;
  white-space: pre-wrap;
  margin: 0;
}
/* AI 분석 영역 */
.analysis-section {
  border-top: 2px solid #e5e7eb;
  padding-top: 24px;
}
.analysis-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.analysis-header h2 { font-size: 1.05rem; margin: 0; }
.analysis-controls { display: flex; align-items: center; gap: 8px; }
.model-select {
  font-family: monospace;
  font-size: 0.78rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 5px 8px;
  color: #374151;
  background: #fff;
  cursor: pointer;
}
.model-select:disabled { opacity: 0.5; cursor: not-allowed; }
.analysis-cost-info {
  font-size: 0.75rem;
  color: #9ca3af;
  white-space: nowrap;
}
.btn-analyze, .btn-reanalyze {
  font-family: monospace;
  font-size: 0.82rem;
  border: none;
  border-radius: 6px;
  padding: 6px 16px;
  cursor: pointer;
}
.btn-analyze {
  background: #6366f1;
  color: #fff;
}
.btn-analyze:not(:disabled):hover { background: #4f46e5; }
.btn-reanalyze {
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}
.btn-reanalyze:not(:disabled):hover { background: #e5e7eb; }
.btn-analyze:disabled, .btn-reanalyze:disabled { opacity: 0.5; cursor: not-allowed; }
.error { color: #ef4444; font-size: 0.85rem; }
.analyzing-placeholder {
  color: #9ca3af;
  font-size: 0.85rem;
  padding: 20px 0;
}
.empty-analysis {
  color: #9ca3af;
  font-size: 0.85rem;
  padding: 12px 0;
}
.analysis-body { display: flex; flex-direction: column; gap: 24px; }
.analysis-block {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px 18px;
}
.analysis-block h3 {
  font-size: 0.88rem;
  font-weight: 700;
  color: #374151;
  margin: 0 0 12px;
}
/* 하이라이트 */
.legend { font-size: 0.78rem; color: #6b7280; margin-bottom: 10px; }
.num-sample { color: #dc2626; font-weight: 600; }
.kw-sample  { color: #2563eb; font-weight: 600; }
.highlighted {
  font-size: 0.85rem;
  line-height: 1.9;
  color: #1f2937;
}
/* 서버에서 내려온 HTML의 span 클래스 스타일 */
.highlighted :deep(.num) { color: #dc2626; }
.highlighted :deep(.kw)  { color: #2563eb; }
/* 키워드 */
.keyword-list { display: flex; flex-direction: column; gap: 10px; }
.keyword-item { display: flex; gap: 10px; align-items: baseline; }
.kw-label {
  font-size: 0.82rem;
  font-weight: 700;
  color: #1f2937;
  white-space: nowrap;
  min-width: 80px;
}
.kw-desc { font-size: 0.82rem; color: #4b5563; line-height: 1.6; }
/* 지원동기 */
.motivation {
  font-size: 0.85rem;
  line-height: 1.85;
  color: #1f2937;
  margin: 0;
  white-space: pre-wrap;
}
/* 질문 */
.question-list {
  padding-left: 20px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.question-list li { font-size: 0.85rem; line-height: 1.7; color: #1f2937; }
.q-text { margin: 0 0 4px; font-weight: 600; }
.q-answer { margin: 0; color: #6b7280; font-style: italic; }
.analyzed-at { font-size: 0.75rem; color: #9ca3af; margin: 0; }
</style>
