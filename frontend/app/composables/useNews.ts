// [컴포저블] 뉴스 스크래핑·조회·분석 API를 호출하는 클라이언트
// useApi()로 baseURL과 쿠키 인증을 자동 처리

export interface ArticleAnalysis {
  highlighted_html: string
  keywords: { keyword: string; explanation: string }[]
  motivation_summary: string
  questions: string[]
  analyzed_at: string
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

  const list = (date: string) =>
    api<Article[]>('/api/v1/news', { query: { date } })

  const get = (id: string) =>
    api<Article>(`/api/v1/news/${id}`)

  const analyze = (id: string) =>
    api<Article>(`/api/v1/news/${id}/analyze`, { method: 'POST' })

  return { scrape, list, get, analyze }
}
