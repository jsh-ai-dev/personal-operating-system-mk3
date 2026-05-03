// [컴포저블] 의미 검색 API 호출을 담당하는 컴포저블
// 검색 질의어를 백엔드로 보내 Qdrant 유사도 검색 결과를 받아오고,
// 전체 인덱싱(기존 대화 임베딩 생성) 요청도 여기서 처리

export interface SearchResult {
  conversation_id: string
  title: string
  model: string
  created_at: string
  score: number
}

export interface SearchResponse {
  results: SearchResult[]
  cost_usd: number
}

export interface IndexResponse {
  indexed: number
  skipped: number
  failed: number
  total: number
  cost_usd: number
}

export const useSearch = () => {
  const api = useApi()

  const search = async (q: string, limit = 10): Promise<SearchResponse> => {
    return api('/api/v1/search', { query: { q, limit } }) as Promise<SearchResponse>
  }

  const indexAll = async (): Promise<IndexResponse> => {
    return api('/api/v1/search/index', { method: 'POST' }) as Promise<IndexResponse>
  }

  return { search, indexAll }
}
