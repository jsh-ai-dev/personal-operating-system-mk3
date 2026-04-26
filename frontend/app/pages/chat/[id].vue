<!-- [페이지] /chat/[id] — 채팅 화면. id가 'new'면 새 대화, 기존 ID면 이어서 대화 -->
<!-- 첫 응답 수신 후 URL을 /chat/new → /chat/{실제ID}로 교체해 새로고침 시 대화가 유지됨 -->

<script setup lang="ts">
import type { Message, OpenAIModel } from '~/composables/useChat'

const route = useRoute()
const router = useRouter()
const { getMessages, getOpenAIModels, chatOpenAI } = useChat()

const isNew = route.params.id === 'new'
const currentConvId = ref<string | null>(isNew ? null : route.params.id as string)

// 기존 대화면 메시지 로드
const messages = ref<Message[]>([])
if (!isNew && currentConvId.value) {
  messages.value = await getMessages(currentConvId.value)
}

const models = await getOpenAIModels()
const selectedModel = ref(models[0]?.id ?? 'gpt-5-nano') // 가격순 정렬된 목록의 첫 번째 = 최저가

const inputText = ref('')
const isStreaming = ref(false)
const streamingContent = ref('')
const errorMessage = ref('')
const messagesEl = ref<HTMLElement>()

let tempId = 0

const scrollToBottom = async () => {
  await nextTick()
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return

  inputText.value = ''
  errorMessage.value = ''
  isStreaming.value = true
  streamingContent.value = ''

  messages.value.push({
    id: `temp-${++tempId}`,
    conversation_id: currentConvId.value ?? '',
    role: 'user',
    content: text,
    model: null,
    tokens_input: null,
    tokens_output: null,
    cost_usd: null,
    created_at: new Date().toISOString(),
  })
  await scrollToBottom()

  await chatOpenAI(
    { conversationId: currentConvId.value, model: selectedModel.value, message: text },
    async (chunk) => {
      streamingContent.value += chunk
      await scrollToBottom()
    },
    async (done) => {
      messages.value.push({
        id: done.message_id,
        conversation_id: done.conversation_id,
        role: 'assistant',
        content: streamingContent.value,
        model: selectedModel.value,
        tokens_input: done.tokens_input,
        tokens_output: done.tokens_output,
        cost_usd: done.cost_usd,
        created_at: new Date().toISOString(),
      })
      streamingContent.value = ''

      if (!currentConvId.value) {
        currentConvId.value = done.conversation_id
        await router.replace(`/chat/${done.conversation_id}`)
      }
      await scrollToBottom()
    },
    (msg) => {
      errorMessage.value = msg
    },
  )

  isStreaming.value = false
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const formatCost = (cost: number | null) => {
  if (cost == null) return ''
  if (cost === 0) return '$0'
  if (cost < 0.0001) return '<$0.0001'
  return `$${cost.toFixed(4)}`
}

const modelLabel = (id: string) => {
  const m = models.find(m => m.id === id)
  if (!m) return id
  return `${id} ($${m.input_per_1m}/$${m.output_per_1m} per 1M)`
}
</script>

<template>
  <div class="page">
    <header class="header">
      <NuxtLink to="/chat" class="back">← 목록으로</NuxtLink>
      <select v-model="selectedModel" class="model-select" :disabled="isStreaming || !!currentConvId">
        <option v-for="m in models" :key="m.id" :value="m.id">{{ modelLabel(m.id) }}</option>
      </select>
    </header>

    <div class="messages" ref="messagesEl">
      <div v-if="messages.length === 0 && !isStreaming" class="placeholder">
        무엇이든 물어보세요
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message"
        :class="msg.role"
      >
        <div class="bubble">{{ msg.content }}</div>
        <div v-if="msg.role === 'assistant' && msg.cost_usd != null" class="msg-meta">
          {{ msg.tokens_input?.toLocaleString() }} in / {{ msg.tokens_output?.toLocaleString() }} out · {{ formatCost(msg.cost_usd) }}
        </div>
      </div>

      <!-- 스트리밍 중인 어시스턴트 응답 -->
      <div v-if="isStreaming && streamingContent" class="message assistant">
        <div class="bubble streaming">{{ streamingContent }}</div>
      </div>
      <div v-else-if="isStreaming && !streamingContent" class="message assistant">
        <div class="bubble typing">···</div>
      </div>
    </div>

    <div v-if="errorMessage" class="error">{{ errorMessage }}</div>

    <div class="input-area">
      <textarea
        v-model="inputText"
        class="input"
        placeholder="메시지 입력 (Shift+Enter 줄바꿈)"
        rows="3"
        :disabled="isStreaming"
        @keydown="handleKeydown"
      />
      <button class="send-btn" :disabled="isStreaming || !inputText.trim()" @click="sendMessage">
        {{ isStreaming ? '···' : '전송' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 0 16px;
  font-family: monospace;
}
.header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}
.back { font-size: 0.85rem; color: #888; text-decoration: none; white-space: nowrap; }
.back:hover { color: #333; }
.model-select {
  font-family: monospace;
  font-size: 0.8rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 4px 8px;
  background: #fff;
  color: #374151;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}
.model-select:disabled { opacity: 0.5; cursor: default; }
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.placeholder { text-align: center; color: #d1d5db; margin-top: 80px; font-size: 0.9rem; }
.message { display: flex; flex-direction: column; }
.message.user { align-items: flex-end; }
.message.assistant { align-items: flex-start; }
.bubble {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.9rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.message.user .bubble { background: #6366f1; color: #fff; border-bottom-right-radius: 4px; }
.message.assistant .bubble { background: #f3f4f6; color: #111; border-bottom-left-radius: 4px; }
.bubble.streaming { opacity: 0.85; }
.bubble.typing { color: #9ca3af; letter-spacing: 4px; }
.msg-meta { font-size: 0.7rem; color: #9ca3af; margin-top: 4px; padding: 0 2px; }
.error {
  padding: 10px 14px;
  margin-bottom: 8px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  color: #dc2626;
  font-size: 0.85rem;
}
.input-area {
  display: flex;
  gap: 10px;
  padding: 16px 0;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0;
}
.input {
  flex: 1;
  font-family: monospace;
  font-size: 0.9rem;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  padding: 10px 12px;
  resize: none;
  outline: none;
  line-height: 1.5;
}
.input:focus { border-color: #6366f1; }
.send-btn {
  padding: 0 20px;
  background: #6366f1;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-family: monospace;
  font-size: 0.9rem;
  cursor: pointer;
  white-space: nowrap;
  align-self: flex-end;
  height: 40px;
}
.send-btn:disabled { opacity: 0.5; cursor: default; }
.send-btn:not(:disabled):hover { background: #4f46e5; }
</style>
