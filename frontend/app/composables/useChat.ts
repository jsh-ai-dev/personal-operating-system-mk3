// [컴포저블] 채팅 API 통신 로직을 컴포넌트로부터 분리한 재사용 함수 모음
// SSE(Server-Sent Events) 스트리밍 파싱 포함 — 컴포넌트는 콜백만 넘기면 됨

export interface QuizQuestion {
  question: string
  options: string[]  // 4개, "A. ..." 형식
  answer: number     // 정답 인덱스 (0~3)
  explanation: string
}

export interface Conversation {
  id: string
  provider: string
  model: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
  total_tokens_input: number
  total_tokens_output: number
  total_cost_usd: number
  summary: string | null
  summary_model: string | null
  summary_cost_usd: number | null
  quiz: QuizQuestion[] | null
  quiz_model: string | null
  quiz_cost_usd: number | null
  tags: string[]
  is_hidden: boolean
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  model: string | null
  tokens_input: number | null
  tokens_output: number | null
  cost_usd: number | null
  created_at: string
  is_hidden: boolean
}

export interface AiModel {
  id: string
  provider: 'openai' | 'claude' | 'gemini'
  // OpenAI / Claude: 가격 기반
  input_per_1m?: number
  output_per_1m?: number
  // Gemini 무료 티어: rate limit 기반
  rpm?: number
  rpd?: number
  tpm?: number
}

export interface ChatDoneEvent {
  conversation_id: string
  message_id: string
  tokens_input: number
  tokens_output: number
  cost_usd: number
}

export const useChat = () => {
  const api = useApi()
  const config = useRuntimeConfig()

  const listConversations = (includeHidden = false) =>
    api<Conversation[]>('/api/v1/chat/conversations', {
      query: includeHidden ? { include_hidden: true } : {},
    })

  const importJetbrainsCodex = () =>
    api<{ imported: number; skipped: number; total: number }>('/api/v1/import/jetbrains-codex', { method: 'POST' })

  const importGeminiTakeout = () =>
    api<{ imported: number; skipped: number; total: number }>('/api/v1/import/gemini-takeout', { method: 'POST' })

  const importClaudeExport = () =>
    api<{ imported: number; skipped: number; total: number }>('/api/v1/import/claude-export', { method: 'POST' })

  const importClaudeCode = () =>
    api<{ imported: number; skipped: number; total: number }>('/api/v1/import/claude-code', { method: 'POST' })

  const setHidden = (id: string, isHidden: boolean) =>
    api(`/api/v1/chat/conversations/${id}`, { method: 'PATCH', body: { is_hidden: isHidden } })

  const setMessageHidden = (id: string, isHidden: boolean) =>
    api(`/api/v1/chat/messages/${id}`, { method: 'PATCH', body: { is_hidden: isHidden } })

  const updateMessageContent = (id: string, content: string) =>
    api(`/api/v1/chat/messages/${id}`, { method: 'PATCH', body: { content } })

  const getConversation = (id: string) =>
    api<Conversation>(`/api/v1/chat/conversations/${id}`)

  const getMessages = (conversationId: string) =>
    api<Message[]>(`/api/v1/chat/conversations/${conversationId}/messages`)

  const getAllModels = async (): Promise<AiModel[]> => {
    let openai: Array<{ id: string; input_per_1m: number; output_per_1m: number }> = []
    let claude: Array<{ id: string; input_per_1m: number; output_per_1m: number }> = []
    let gemini: Array<{ id: string; rpm: number; rpd: number; tpm: number }> = []
    try { openai = await api('/api/v1/chat/openai/models') } catch (_) {}
    try { claude = await api('/api/v1/chat/claude/models') } catch (_) {}
    try { gemini = await api('/api/v1/chat/gemini/models') } catch (_) {}

    // 순서: OpenAI → Claude → Gemini (각 그룹 내 가격 오름차순)
    return [
      ...openai.map((m): AiModel => ({ ...m, provider: 'openai' })),
      ...claude.map((m): AiModel => ({ ...m, provider: 'claude' })),
      ...gemini.map((m): AiModel => ({ ...m, provider: 'gemini' })),
    ]
  }

  // SSE 스트리밍 공통 처리 — endpoint만 다르고 포맷은 동일
  const _streamChat = async (
    endpoint: string,
    params: { conversationId: string | null; model: string; message: string },
    onChunk: (content: string) => void,
    onDone: (data: ChatDoneEvent) => void,
    onError: (message: string) => void,
  ) => {
    const response = await fetch(`${config.public.apiBase}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: params.conversationId,
        model: params.model,
        message: params.message,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }))
      onError(err.detail ?? `HTTP ${response.status}`)
      return
    }

    if (!response.body) {
      onError('응답 스트림을 받지 못했습니다')
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'chunk') onChunk(data.content)
          else if (data.type === 'done') onDone(data as ChatDoneEvent)
          else if (data.type === 'error') onError(data.message)
        } catch {}
      }
    }
  }

  const chatOpenAI = (
    params: { conversationId: string | null; model: string; message: string },
    onChunk: (content: string) => void,
    onDone: (data: ChatDoneEvent) => void,
    onError: (message: string) => void,
  ) => _streamChat('/api/v1/chat/openai', params, onChunk, onDone, onError)

  const chatGemini = (
    params: { conversationId: string | null; model: string; message: string },
    onChunk: (content: string) => void,
    onDone: (data: ChatDoneEvent) => void,
    onError: (message: string) => void,
  ) => _streamChat('/api/v1/chat/gemini', params, onChunk, onDone, onError)

  const chatClaude = (
    params: { conversationId: string | null; model: string; message: string },
    onChunk: (content: string) => void,
    onDone: (data: ChatDoneEvent) => void,
    onError: (message: string) => void,
  ) => _streamChat('/api/v1/chat/claude', params, onChunk, onDone, onError)

  const summarizeConversation = (id: string, model: string) =>
    api<{ summary: string; tokens_input: number; tokens_output: number; cost_usd: number }>(
      `/api/v1/chat/conversations/${id}/summary`,
      { method: 'POST', body: { model } },
    )

  const generateQuiz = (id: string, model: string) =>
    api<{ quiz: QuizQuestion[]; tokens_input: number; tokens_output: number; cost_usd: number }>(
      `/api/v1/chat/conversations/${id}/quiz`,
      { method: 'POST', body: { model } },
    )

  return { listConversations, getConversation, getMessages, getAllModels, chatOpenAI, chatGemini, chatClaude, summarizeConversation, generateQuiz, importJetbrainsCodex, importGeminiTakeout, importClaudeExport, importClaudeCode, setHidden, setMessageHidden, updateMessageContent }
}
