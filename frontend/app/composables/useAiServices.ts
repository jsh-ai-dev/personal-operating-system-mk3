// [AI 서비스 컴포저블] AI 서비스 CRUD 관련 API 호출 함수와 타입을 제공하는 파일
// useApi()를 활용해 백엔드 /api/v1/ai-services 엔드포인트와 통신함

// AI 서비스 데이터 타입
export interface AIService {
  id: string
  name: string
  plan_name: string | null
  monthly_cost: number | null
  currency: string
  billing_day: number | null
  next_billing_date: string | null
  usage_limit: number | null
  usage_current: number | null
  usage_unit: string | null
  billing_url: string | null
  notes: string | null
}

// id를 제외한 입력 타입 (생성/수정 시 사용)
export type AIServiceForm = Omit<AIService, 'id'>

// AI 서비스 CRUD API를 호출하는 컴포저블
export const useAiServices = () => {
  const api = useApi()

  const list = () =>
    api<AIService[]>('/api/v1/ai-services')

  const get = (id: string) =>
    api<AIService>(`/api/v1/ai-services/${id}`)

  const create = (data: AIServiceForm) =>
    api<AIService>('/api/v1/ai-services', { method: 'POST', body: data })

  const update = (id: string, data: AIServiceForm) =>
    api<AIService>(`/api/v1/ai-services/${id}`, { method: 'PUT', body: data })

  const remove = (id: string) =>
    api(`/api/v1/ai-services/${id}`, { method: 'DELETE' })

  // Claude.ai 스크래퍼를 실행하고 DB를 갱신함
  const syncClaude = () =>
    api('/api/v1/scraper/claude', { method: 'POST' })

  // ChatGPT 스크래퍼를 실행하고 DB를 갱신함
  const syncChatGPT = () =>
    api('/api/v1/scraper/chatgpt', { method: 'POST' })

  const syncCodex = () =>
    api('/api/v1/scraper/codex', { method: 'POST' })

  const syncGemini = () =>
    api('/api/v1/scraper/gemini', { method: 'POST' })

  const syncCursor = () =>
    api('/api/v1/scraper/cursor', { method: 'POST' })

  return { list, get, create, update, remove, syncClaude, syncChatGPT, syncCodex, syncGemini, syncCursor }
}
