<!-- [페이지] /chat — 전체 대화 목록 페이지. 각 항목 클릭 시 /chat/[id]로 이동 -->

<script setup lang="ts">
const { listConversations, setHidden, importJetbrainsCodex } = useChat()

// refresh는 runImport에서 참조하므로 먼저 선언
const showHidden = ref(false)
const { data: conversations, refresh } = await useAsyncData(
  'conversations',
  () => listConversations(showHidden.value),
)

const importing = ref(false)
const importResult = ref('')

const runImport = async () => {
  importing.value = true
  importResult.value = ''
  try {
    const result = await importJetbrainsCodex()
    importResult.value = result.imported > 0
      ? `${result.imported}개 가져옴`
      : '이미 최신 상태'
    if (result.imported > 0) await refresh()
  } catch (e) {
    importResult.value = '오류 발생'
  } finally {
    importing.value = false
    setTimeout(() => { importResult.value = '' }, 3000)
  }
}

const toggleShowHidden = async () => {
  showHidden.value = !showHidden.value
  await refresh()
}

const hide = async (e: Event, id: string) => {
  e.preventDefault()
  await setHidden(id, true)
  await refresh()
}

const unhide = async (e: Event, id: string) => {
  e.preventDefault()
  await setHidden(id, false)
  await refresh()
}

const formatCost = (cost: number) =>
  cost === 0 ? '$0' : cost < 0.0001 ? '<$0.0001' : `$${cost.toFixed(4)}`

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

const providerLabel = (provider: string) =>
  ({ openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', gemini: 'Gemini', jetbrains: 'JetBrains' })[provider] ?? provider
</script>

<template>
  <main>
    <header class="header">
      <h1>AI Chat</h1>
      <div class="header-actions">
        <button class="btn-toggle-hidden" :class="{ active: showHidden }" @click="toggleShowHidden">
          {{ showHidden ? '숨김 숨기기' : '숨김 보기' }}
        </button>
        <button class="btn-import" :disabled="importing" @click="runImport">
          {{ importing ? '가져오는 중…' : 'Codex 가져오기' }}
        </button>
        <span v-if="importResult" class="import-result">{{ importResult }}</span>
        <NuxtLink to="/chat/new" class="btn-new">+ 새 대화</NuxtLink>
      </div>
    </header>

    <div v-if="conversations?.length" class="list">
      <div v-for="conv in conversations" :key="conv.id" class="conv-row">
        <NuxtLink :to="`/chat/${conv.id}`" class="conv-item">
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
        <button v-if="!conv.is_hidden" class="btn-hide" @click="hide($event, conv.id)" title="숨기기">✕</button>
        <button v-else class="btn-unhide" @click="unhide($event, conv.id)" title="숨김 취소">↩</button>
      </div>
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
.header-actions { display: flex; align-items: center; gap: 8px; }
.btn-new {
  padding: 6px 14px;
  border: 1px solid #6366f1;
  border-radius: 6px;
  color: #6366f1;
  text-decoration: none;
  font-size: 0.85rem;
}
.btn-new:hover { background: #eef2ff; }
.btn-toggle-hidden {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: none;
  color: #6b7280;
  font-family: monospace;
  font-size: 0.85rem;
  cursor: pointer;
}
.btn-toggle-hidden:hover { border-color: #9ca3af; color: #374151; }
.btn-toggle-hidden.active { border-color: #6366f1; color: #6366f1; background: #eef2ff; }
.btn-import {
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: none;
  color: #6b7280;
  font-family: monospace;
  font-size: 0.85rem;
  cursor: pointer;
}
.btn-import:hover:not(:disabled) { border-color: #9ca3af; color: #374151; }
.btn-import:disabled { opacity: 0.5; cursor: default; }
.import-result { font-size: 0.8rem; color: #059669; }
.list { display: flex; flex-direction: column; gap: 8px; }
.conv-row { display: flex; align-items: stretch; gap: 6px; }
.conv-item {
  flex: 1;
  display: block;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s;
  min-width: 0;
}
.conv-item:hover { border-color: #6366f1; }
.btn-hide {
  flex-shrink: 0;
  width: 32px;
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #d1d5db;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-hide:hover { border-color: #f87171; color: #f87171; background: #fef2f2; }
.btn-unhide {
  flex-shrink: 0;
  width: 32px;
  background: #eef2ff;
  border: 1px solid #6366f1;
  border-radius: 8px;
  color: #6366f1;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-unhide:hover { background: #e0e7ff; }
/* 숨긴 항목은 흐리게 표시 */
.conv-row:has(.btn-unhide) .conv-item { opacity: 0.45; }
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
