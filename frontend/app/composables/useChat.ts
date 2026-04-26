// [컴포저블] 채팅 API 통신 로직을 컴포넌트로부터 분리한 재사용 함수 모음
// SSE(Server-Sent Events) 스트리밍 파싱 포함 — 컴포넌트는 콜백만 넘기면 됨

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

export interface OpenAIModel {
  id: string
  input_per_1m: number
  output_per_1m: number
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

  const setHidden = (id: string, isHidden: boolean) =>
    api(`/api/v1/chat/conversations/${id}`, { method: 'PATCH', body: { is_hidden: isHidden } })

  const setMessageHidden = (id: string, isHidden: boolean) =>
    api(`/api/v1/chat/messages/${id}`, { method: 'PATCH', body: { is_hidden: isHidden } })

  const updateMessageContent = (id: string, content: string) =>
    api(`/api/v1/chat/messages/${id}`, { method: 'PATCH', body: { content } })

  const getMessages = (conversationId: string) =>
    api<Message[]>(`/api/v1/chat/conversations/${conversationId}/messages`)

  const getOpenAIModels = () =>
    api<OpenAIModel[]>('/api/v1/chat/openai/models')

  const chatOpenAI = async (
    params: { conversationId: string | null; model: string; message: string },
    onChunk: (content: string) => void,
    onDone: (data: ChatDoneEvent) => void,
    onError: (message: string) => void,
  ) => {
    const response = await fetch(`${config.public.apiBase}/api/v1/chat/openai`, {
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

  return { listConversations, getMessages, getOpenAIModels, chatOpenAI, setHidden, setMessageHidden, updateMessageContent }
}
