<script setup lang="ts">
import type { Conversation } from '~/composables/useChat'

const { listConversations } = useChat()
const { data: conversations } = await useAsyncData('conversations', listConversations)

const formatCost = (cost: number) =>
  cost === 0 ? '$0' : cost < 0.0001 ? '<$0.0001' : `$${cost.toFixed(4)}`

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

const providerLabel = (provider: string) =>
  ({ openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google' })[provider] ?? provider
</script>

<template>
  <main>
    <header class="header">
      <h1>AI Chat</h1>
      <NuxtLink to="/chat/new" class="btn-new">+ 새 대화</NuxtLink>
    </header>

    <div v-if="conversations?.length" class="list">
      <NuxtLink
        v-for="conv in conversations"
        :key="conv.id"
        :to="`/chat/${conv.id}`"
        class="conv-item"
      >
        <div class="conv-meta">
          <span class="badge" :class="conv.provider">{{ providerLabel(conv.provider) }}</span>
          <span class="model">{{ conv.model }}</span>
          <span class="cost">{{ formatCost(conv.total_cost_usd) }}</span>
          <span class="tokens">{{ (conv.total_tokens_input + conv.total_tokens_output).toLocaleString() }} tokens</span>
        </div>
        <div class="conv-title">{{ conv.title }}</div>
        <div class="conv-stats">
          메시지 {{ conv.message_count }}개 · {{ formatDate(conv.updated_at) }}
        </div>
      </NuxtLink>
    </div>

    <div v-else class="empty">
      대화 기록이 없습니다.
      <NuxtLink to="/chat/new">새 대화 시작 →</NuxtLink>
    </div>
  </main>
</template>

<style scoped>
main {
  max-width: 720px;
  margin: 40px auto;
  padding: 0 24px;
  font-family: monospace;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}
h1 { font-size: 1.3rem; margin: 0; }
.btn-new {
  padding: 6px 14px;
  border: 1px solid #6366f1;
  border-radius: 6px;
  color: #6366f1;
  text-decoration: none;
  font-size: 0.85rem;
}
.btn-new:hover { background: #eef2ff; }
.list { display: flex; flex-direction: column; gap: 8px; }
.conv-item {
  display: block;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s;
}
.conv-item:hover { border-color: #6366f1; }
.conv-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 0.75rem;
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
.model { color: #6b7280; }
.cost { color: #059669; font-weight: 600; }
.tokens { color: #9ca3af; }
.conv-title { font-size: 0.9rem; color: #111; margin-bottom: 4px; }
.conv-stats { font-size: 0.75rem; color: #9ca3af; }
.empty { text-align: center; color: #aaa; font-size: 0.9rem; margin-top: 80px; }
.empty a { color: #6366f1; text-decoration: none; margin-left: 4px; }
</style>
