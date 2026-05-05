// [컴포저블] 뉴스 스크래핑·조회·분석 API를 호출하는 클라이언트
// useApi()로 baseURL과 쿠키 인증을 자동 처리

export interface NewsModel {
  id: string
  input_per_1m: number
  output_per_1m: number
}

export interface ArticleAnalysis {
  highlighted_html: string
  keywords: { keyword: string; explanation: string }[]
  motivation_summary: string
  questions: { question: string; expected_answer: string }[]
  analyzed_at: string
  analysis_model: string
  analysis_cost_usd: number
}

export interface Article {
  id: string
  date: string
  page_num: number
  title: string
  url: string
  content: string
  companies: string[]
  tags: string[]
  scraped_at: string
  analysis: ArticleAnalysis | null
}

export const useNews = () => {
  const api = useApi()

  const scrape = (date: string) =>
    api<Article[]>('/api/v1/news/scrape', { method: 'POST', body: { date } })

  const list = (params: { date?: string; company?: string; tag?: string }) =>
    api<Article[]>('/api/v1/news', { query: params })

  const get = (id: string) =>
    api<Article>(`/api/v1/news/${id}`)

  const getFilterOptions = () =>
    api<{ companies: string[]; tags: string[] }>('/api/v1/news/filter-options')

  const getModels = () =>
    api<NewsModel[]>('/api/v1/news/models')

  const analyze = (id: string, model: string) =>
    api<Article>(`/api/v1/news/${id}/analyze`, { method: 'POST', body: { model } })

  return { scrape, list, get, getFilterOptions, getModels, analyze }
}
