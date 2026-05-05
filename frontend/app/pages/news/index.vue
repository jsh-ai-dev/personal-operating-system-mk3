<!-- [페이지] /news — 신문 스크랩 목록 -->
<!-- 날짜 선택 후 스크랩 실행, 면·기업명·태그 필터링 지원 -->

<script setup lang="ts">
import type { Article } from '~/composables/useNews'

const { scrape, list, getFilterOptions } = useNews()
const route = useRoute()

const today = new Date().toISOString().slice(0, 10)
const selectedDate = ref((route.query.date as string) || today)
const articles = ref<Article[]>([])
const allCompanies = ref<string[]>([])
const allTags = ref<string[]>([])
const loading = ref(false)
const scraping = ref(false)
const error = ref('')

const filterCompany = ref('all')
const filterTag = ref('all')
const isFiltered = computed(() => filterCompany.value !== 'all' || filterTag.value !== 'all')

// 날짜 뷰: 면 기준 그룹핑 (필터 미적용 시)
const grouped = computed(() => {
  const map = new Map<number, Article[]>()
  for (const a of articles.value) {
    const arr = map.get(a.page_num) ?? []
    arr.push(a)
    map.set(a.page_num, arr)
  }
  return [...map.entries()].sort((a, b) => a[0] - b[0])
})

// 필터 뷰: 날짜 기준 그룹핑 (최신순, 필터 적용 시)
const groupedByDate = computed(() => {
  const map = new Map<string, Article[]>()
  for (const a of articles.value) {
    const arr = map.get(a.date) ?? []
    arr.push(a)
    map.set(a.date, arr)
  }
  return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]))
})

const loadArticles = async () => {
  loading.value = true
  error.value = ''
  try {
    if (isFiltered.value) {
      articles.value = await list({
        company: filterCompany.value !== 'all' ? filterCompany.value : undefined,
        tag: filterTag.value !== 'all' ? filterTag.value : undefined,
      })
    } else {
      articles.value = await list({ date: selectedDate.value })
    }
  } catch {
    articles.value = []
  } finally {
    loading.value = false
  }
}

const loadFilterOptions = async () => {
  try {
    const opts = await getFilterOptions()
    allCompanies.value = opts.companies
    allTags.value = opts.tags
  } catch {}
}

// 날짜 변경: 필터가 없을 때만 재조회 (필터가 있으면 필터가 우선)
watch(selectedDate, () => { if (!isFiltered.value) loadArticles() })

// 필터 변경: 항상 재조회
watch([filterCompany, filterTag], loadArticles)

const onScrape = async () => {
  scraping.value = true
  error.value = ''
  try {
    articles.value = await scrape(selectedDate.value)
    // 스크랩 후 분석이 완료되면 새 기업/태그가 생길 수 있으므로 옵션 갱신
    await loadFilterOptions()
  } catch (e: any) {
    error.value = e.data?.detail ?? '스크랩 중 오류가 발생했습니다.'
  } finally {
    scraping.value = false
  }
}

onMounted(() => {
  loadArticles()
  loadFilterOptions()
})
</script>

<template>
  <main>
    <header class="header">
      <h1>신문 스크랩</h1>
      <div class="header-actions">
        <input
          v-model="selectedDate"
          type="date"
          class="date-input"
        />
        <button class="btn-scrape" :disabled="scraping" @click="onScrape">
          {{ scraping ? '수집 중…' : '스크랩' }}
        </button>
      </div>
    </header>

    <div class="filters">
      <select v-model="filterCompany" class="filter-select">
        <option value="all">전체 기업</option>
        <option v-for="c in allCompanies" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="filterTag" class="filter-select">
        <option value="all">전체 태그</option>
        <option v-for="t in allTags" :key="t" :value="t">{{ t }}</option>
      </select>
      <span class="count">
        {{ articles.length }}건
        <span v-show="isFiltered" class="count-scope">· 전체 기간</span>
      </span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-show="loading" class="empty">불러오는 중…</div>

    <div v-show="!loading && articles.length === 0 && !scraping" class="empty">
      <p>{{ selectedDate }} 날짜의 기사가 없습니다.</p>
      <p>스크랩 버튼을 눌러 수집하세요.</p>
    </div>

    <!-- 날짜 뷰: 면 기준 그룹핑 -->
    <div v-show="!isFiltered">
      <div v-for="[pageNum, items] in grouped" :key="pageNum" class="section">
        <h2 class="page-label">{{ pageNum }}면</h2>
        <div class="article-list">
          <NuxtLink
            v-for="a in items"
            :key="a.id"
            :to="`/news/${a.id}?date=${selectedDate}`"
            class="article-card"
          >
            <div class="article-meta">
              <span class="page-badge">{{ a.page_num }}면</span>
              <span class="date-text">{{ a.date }}</span>
              <span v-if="a.analysis" class="analyzed-badge">분석완료</span>
            </div>
            <p class="article-title">{{ a.title }}</p>
            <div class="article-tags">
              <span v-for="c in a.companies" :key="c" class="tag company">{{ c }}</span>
              <span v-for="t in a.tags" :key="t" class="tag topic">{{ t }}</span>
            </div>
          </NuxtLink>
        </div>
      </div>
    </div>

    <!-- 필터 뷰: 날짜 기준 그룹핑 (전체 기간) -->
    <div v-show="isFiltered">
      <div v-for="[date, items] in groupedByDate" :key="date" class="section">
        <h2 class="page-label">{{ date }}</h2>
        <div class="article-list">
          <NuxtLink
            v-for="a in items"
            :key="a.id"
            :to="`/news/${a.id}?date=${a.date}`"
            class="article-card"
          >
            <div class="article-meta">
              <span class="page-badge">{{ a.page_num }}면</span>
              <span class="date-text">{{ a.date }}</span>
              <span v-if="a.analysis" class="analyzed-badge">분석완료</span>
            </div>
            <p class="article-title">{{ a.title }}</p>
            <div class="article-tags">
              <span v-for="c in a.companies" :key="c" class="tag company">{{ c }}</span>
              <span v-for="t in a.tags" :key="t" class="tag topic">{{ t }}</span>
            </div>
          </NuxtLink>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
main {
  max-width: 780px;
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
h1 { font-size: 1.3rem; margin: 0; }
.header-actions { display: flex; align-items: center; gap: 10px; }
.date-input {
  font-family: monospace;
  font-size: 0.85rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 5px 10px;
  color: #374151;
}
.btn-scrape {
  font-family: monospace;
  font-size: 0.85rem;
  background: #6366f1;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 16px;
  cursor: pointer;
}
.btn-scrape:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-scrape:not(:disabled):hover { background: #4f46e5; }
.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.filter-select {
  font-family: monospace;
  font-size: 0.82rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 5px 10px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}
.count { font-size: 0.8rem; color: #9ca3af; }
.count-scope { color: #6366f1; }
.error { color: #ef4444; font-size: 0.85rem; margin-bottom: 12px; }
.empty {
  text-align: center;
  color: #9ca3af;
  font-size: 0.88rem;
  margin-top: 60px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
}
.section { margin-bottom: 28px; }
.page-label {
  font-size: 0.9rem;
  font-weight: 700;
  color: #6b7280;
  margin: 0 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e5e7eb;
}
.article-list { display: flex; flex-direction: column; gap: 8px; }
.article-card {
  display: block;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 14px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s;
}
.article-card:hover { border-color: #6366f1; }
.article-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.page-badge {
  font-size: 0.7rem;
  background: #ede9fe;
  color: #5b21b6;
  border-radius: 4px;
  padding: 2px 6px;
  font-weight: 600;
}
.date-text { font-size: 0.75rem; color: #9ca3af; }
.analyzed-badge {
  font-size: 0.7rem;
  background: #d1fae5;
  color: #065f46;
  border-radius: 4px;
  padding: 2px 6px;
  font-weight: 600;
}
.article-title {
  font-size: 0.92rem;
  color: #111;
  margin: 0 0 8px;
  line-height: 1.5;
}
.article-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.tag {
  font-size: 0.72rem;
  border-radius: 4px;
  padding: 2px 7px;
}
.tag.company { background: #dbeafe; color: #1e40af; }
.tag.topic   { background: #f3f4f6; color: #374151; }
</style>
