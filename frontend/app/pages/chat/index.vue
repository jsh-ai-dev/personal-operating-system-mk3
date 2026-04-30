<!-- [페이지] /chat — 전체 대화 목록 페이지. 각 항목 클릭 시 /chat/[id]로 이동 -->

<script setup lang="ts">
const { listConversations, setHidden, deleteConversation, importJetbrainsCodex, importGeminiTakeout, importClaudeExport, importClaudeCode } = useChat()

// refresh는 runImport에서 참조하므로 먼저 선언
const showHidden = ref(false)
const { data: conversations, refresh } = await useAsyncData(
  'conversations',
  () => listConversations(showHidden.value),
)

const importingCodex = ref(false)
const importingGemini = ref(false)
const importingClaude = ref(false)
const importingClaudeCode = ref(false)
const importResult = ref('')
const importModalOpen = ref(false)
const selectedImportKey = ref<'jetbrains-codex' | 'claude-export' | 'claude-code' | 'gemini-takeout'>('jetbrains-codex')

const importOptions = [
  { label: 'ChatGPT', key: 'chatgpt', enabled: false },
  { label: 'Codex', key: 'jetbrains-codex', enabled: true },
  { label: 'Gemini', key: 'gemini-takeout', enabled: true },
  { label: 'Gemini Code Assist', key: 'gemini-code-assist', enabled: false },
  { label: 'Claude', key: 'claude-export', enabled: true },
  { label: 'Claude Code', key: 'claude-code', enabled: true },
  { label: 'Copilot', key: 'copilot', enabled: false },
  { label: 'Cursor', key: 'cursor', enabled: false },
] as const

type FilterKey =
  | 'openai'
  | 'anthropic'
  | 'google'
  | 'jetbrains-codex'
  | 'claude-export'
  | 'claude-code'
  | 'chatgpt'
  | 'gemini-code-assist'
  | 'copilot'
  | 'cursor'

const filterOptions: Array<{ key: FilterKey; label: string; emoji: string }> = [
  { key: 'openai', label: 'OpenAI', emoji: '🧠' },
  { key: 'anthropic', label: 'Claude API', emoji: '🧡' },
  { key: 'google', label: 'Gemini API', emoji: '🔷' },
  { key: 'jetbrains-codex', label: 'Codex', emoji: '🛠️' },
  { key: 'claude-export', label: 'Claude', emoji: '🟠' },
  { key: 'claude-code', label: 'Claude Code', emoji: '💻' },
  { key: 'chatgpt', label: 'ChatGPT', emoji: '💬' },
  { key: 'gemini-code-assist', label: 'Gemini Code Assist', emoji: '🧩' },
  { key: 'copilot', label: 'Copilot', emoji: '🛫' },
  { key: 'cursor', label: 'Cursor', emoji: '⌨️' },
]
const activeFilters = ref<FilterKey[]>([])
const dateFrom = ref('')
const dateTo = ref('')
const selectedPreset = ref<'7d' | '30d' | 'month' | null>(null)

const dateOnly = (d: Date) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
const applyRangePreset = (preset: '7d' | '30d' | 'month') => {
  const now = new Date()
  const end = dateOnly(now)
  if (preset === 'month') {
    const start = new Date(now.getFullYear(), now.getMonth(), 1)
    dateFrom.value = dateOnly(start)
    dateTo.value = end
    selectedPreset.value = preset
    return
  }
  const days = preset === '7d' ? 6 : 29
  const start = new Date(now)
  start.setDate(start.getDate() - days)
  dateFrom.value = dateOnly(start)
  dateTo.value = end
  selectedPreset.value = preset
}

const _runImport = async (fn: () => Promise<{ imported: number; skipped: number; total: number }>, setLoading: (v: boolean) => void) => {
  setLoading(true)
  importResult.value = ''
  try {
    const result = await fn()
    importResult.value = result.imported > 0 ? `${result.imported}개 가져옴` : '이미 최신 상태'
    if (result.imported > 0) await refresh()
  } catch (e) {
    importResult.value = '오류 발생'
  } finally {
    setLoading(false)
    setTimeout(() => { importResult.value = '' }, 3000)
  }
}

const runImportCodex = () => _runImport(importJetbrainsCodex, v => { importingCodex.value = v })
const runImportGemini = () => _runImport(importGeminiTakeout, v => { importingGemini.value = v })
const runImportClaude = () => _runImport(importClaudeExport, v => { importingClaude.value = v })
const runImportClaudeCode = () => _runImport(importClaudeCode, v => { importingClaudeCode.value = v })

const runImportByKey = async () => {
  if (selectedImportKey.value === 'jetbrains-codex') await runImportCodex()
  if (selectedImportKey.value === 'claude-export') await runImportClaude()
  if (selectedImportKey.value === 'claude-code') await runImportClaudeCode()
  if (selectedImportKey.value === 'gemini-takeout') await runImportGemini()
  importModalOpen.value = false
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

const removeConversation = async (e: Event, id: string) => {
  e.preventDefault()
  if (!confirm('이 대화 내역을 완전히 삭제할까요?')) return
  await deleteConversation(id)
  await refresh()
}

const formatCost = (cost: number) =>
  cost === 0 ? '$0' : cost < 0.0001 ? '<$0.0001' : `$${cost.toFixed(4)}`

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ko-KR', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

// 소스 레이블 — 임포트는 모델값 기준, API는 provider 기준
const convSourceLabel = (conv: { provider: string; model: string }): string => {
  const labels: Record<string, string> = {
    'codex': 'JetBrains',
    'claude-code': 'Claude Code',
    'claude': 'Claude.ai',
    'gemini': 'Gemini',
  }
  if (labels[conv.model]) return labels[conv.model]
  return ({ openai: 'OpenAI', anthropic: 'Claude', google: 'Gemini' })[conv.provider] ?? conv.provider
}

// 대화 타입 — API(직접 호출) / 채팅 임포트(구독 서비스) / 코딩 임포트(코딩 어시스턴트)
const convType = (conv: { model: string }): { label: string; cls: string } => {
  if (conv.model === 'codex' || conv.model === 'claude-code')
    return { label: '코딩', cls: 'type-code' }
  if (conv.model === 'claude' || conv.model === 'gemini')
    return { label: '채팅 임포트', cls: 'type-chat' }
  return { label: 'API', cls: 'type-api' }
}

const convFilterKey = (conv: { provider: string; model: string }): FilterKey => {
  if (conv.model === 'codex') return 'jetbrains-codex'
  if (conv.model === 'claude-code') return 'claude-code'
  if (conv.model === 'claude') return 'claude-export'
  if (conv.model === 'gemini') return 'gemini-takeout'
  if (conv.provider === 'openai') return 'openai'
  if (conv.provider === 'anthropic') return 'anthropic'
  if (conv.provider === 'google') return 'google'
  return 'openai'
}

const toggleFilter = (key: FilterKey) => {
  const set = new Set(activeFilters.value)
  if (set.has(key)) set.delete(key)
  else set.add(key)
  activeFilters.value = [...set]
}

const filteredConversations = computed(() => {
  const rows = conversations.value ?? []
  const serviceFiltered =
    activeFilters.value.length === 0
      ? rows
      : rows.filter((c) => activeFilters.value.includes(convFilterKey(c)))
  return serviceFiltered.filter((c) => {
    const created = new Date(c.created_at)
    if (Number.isNaN(created.getTime())) return false
    if (dateFrom.value) {
      const from = new Date(`${dateFrom.value}T00:00:00`)
      if (created < from) return false
    }
    if (dateTo.value) {
      const to = new Date(`${dateTo.value}T23:59:59.999`)
      if (created > to) return false
    }
    return true
  })
})
</script>

<template>
  <main>
    <header class="header">
      <h1>AI Chat</h1>
      <div class="header-actions">
        <button class="btn-toggle-hidden" :class="{ active: showHidden }" @click="toggleShowHidden">
          {{ showHidden ? '숨김 숨기기' : '숨김 보기' }}
        </button>
        <button class="btn-import" :disabled="importingCodex || importingGemini || importingClaude || importingClaudeCode" @click="importModalOpen = true">
          내역 가져오기
        </button>
        <span v-if="importResult" class="import-result">{{ importResult }}</span>
        <NuxtLink to="/chat/new" class="btn-new">+ 새 대화</NuxtLink>
      </div>
    </header>
    <div v-if="importModalOpen" class="modal-overlay">
      <div class="modal">
        <p class="modal-title">가져올 서비스 선택</p>
        <select v-model="selectedImportKey" class="modal-select" :disabled="importingCodex || importingGemini || importingClaude || importingClaudeCode">
          <option v-for="opt in importOptions" :key="opt.key" :value="opt.key" :disabled="!opt.enabled">
            {{ opt.label }} {{ opt.enabled ? '' : '(준비 중...)' }}
          </option>
        </select>
        <p class="modal-hint">현재 구현된 항목만 선택 가능합니다.</p>
        <div class="modal-actions">
          <button class="btn-import" @click="importModalOpen = false">취소</button>
          <button class="btn-import" :disabled="importingCodex || importingGemini || importingClaude || importingClaudeCode || !importOptions.find(v => v.key === selectedImportKey)?.enabled" @click="runImportByKey">
            가져오기
          </button>
        </div>
      </div>
    </div>
    <div class="filter-row">
      <button
        v-for="f in filterOptions"
        :key="f.key"
        class="filter-chip"
        :class="{ active: activeFilters.includes(f.key) }"
        @click="toggleFilter(f.key)"
      >
        {{ f.emoji }} {{ f.label }}
      </button>
      <button class="filter-clear" @click="activeFilters = []">선택 해제</button>
    </div>
    <div class="date-filter-row">
      <label class="date-label">
        시작일
        <input v-model="dateFrom" class="date-input" type="date" @change="selectedPreset = null">
      </label>
      <label class="date-label">
        종료일
        <input v-model="dateTo" class="date-input" type="date" @change="selectedPreset = null">
      </label>
      <button class="preset-btn" :class="{ active: selectedPreset === '7d' }" @click="applyRangePreset('7d')">최근 7일</button>
      <button class="preset-btn" :class="{ active: selectedPreset === '30d' }" @click="applyRangePreset('30d')">최근 30일</button>
      <button class="preset-btn" :class="{ active: selectedPreset === 'month' }" @click="applyRangePreset('month')">이번 달</button>
      <button class="filter-clear" @click="dateFrom = ''; dateTo = ''; selectedPreset = null">기간 해제</button>
    </div>

    <div v-if="filteredConversations?.length" class="list">
      <div v-for="conv in filteredConversations" :key="conv.id" class="conv-row">
        <NuxtLink :to="`/chat/${conv.id}`" class="conv-item">
          <div class="conv-meta">
            <span class="badge" :class="conv.provider">{{ convSourceLabel(conv) }}</span>
            <span class="type-tag" :class="convType(conv).cls">{{ convType(conv).label }}</span>
            <span class="model">{{ conv.model }}</span>
            <span class="cost">{{ formatCost(conv.total_cost_usd) }}</span>
            <span class="tokens">{{ (conv.total_tokens_input + conv.total_tokens_output).toLocaleString() }} tokens</span>
          </div>
          <div class="conv-title">{{ conv.title }}</div>
          <div class="conv-stats">
            메시지 {{ conv.message_count }}개 · 생성 {{ formatDate(conv.created_at) }}
          </div>
        </NuxtLink>
        <div class="side-actions">
          <button v-if="!conv.is_hidden" class="btn-hide" @click="hide($event, conv.id)" title="숨기기">숨김</button>
          <button v-else class="btn-unhide" @click="unhide($event, conv.id)" title="숨김 취소">복원</button>
          <button class="btn-delete" @click="removeConversation($event, conv.id)" title="삭제">삭제</button>
        </div>
      </div>
    </div>

    <div v-else class="empty">
      조건에 맞는 대화 기록이 없습니다.
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
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgb(0 0 0 / 40%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  width: 320px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
}
.modal-title { margin: 0 0 8px; font-size: 0.88rem; color: #111; font-weight: 700; }
.modal-select {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 6px 8px;
  font-family: monospace;
  font-size: 0.82rem;
}
.modal-hint { margin: 8px 0 0; font-size: 0.76rem; color: #9ca3af; }
.modal-actions { margin-top: 10px; display: flex; justify-content: flex-end; gap: 8px; }
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.date-filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.date-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #6b7280;
  font-size: 0.75rem;
}
.date-input {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 4px 8px;
  font-family: monospace;
  font-size: 0.75rem;
}
.preset-btn {
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-family: monospace;
  font-size: 0.75rem;
  padding: 4px 10px;
  cursor: pointer;
  transition: transform 0.06s ease, box-shadow 0.12s ease, background-color 0.12s ease;
}
.preset-btn.active {
  border-color: #6366f1;
  background: #eef2ff;
  color: #4f46e5;
}
.preset-btn:active {
  transform: translateY(1px) scale(0.98);
  background: #e2e8f0;
}
.filter-chip,
.filter-clear {
  border: 1px solid #d1d5db;
  border-radius: 999px;
  background: #fff;
  color: #374151;
  font-family: monospace;
  font-size: 0.75rem;
  padding: 4px 9px;
  cursor: pointer;
  transition: transform 0.06s ease, box-shadow 0.12s ease, background-color 0.12s ease;
}
.filter-chip.active {
  border-color: #6366f1;
  background: #eef2ff;
  color: #4f46e5;
}
.filter-chip:active {
  transform: translateY(1px) scale(0.98);
  background: #e2e8f0;
}
.filter-clear {
  border-style: dashed;
  transition: transform 0.06s ease, box-shadow 0.12s ease, background-color 0.12s ease;
}
.filter-clear:active {
  transform: translateY(1px) scale(0.98);
  background: #e2e8f0;
}
.list { display: flex; flex-direction: column; gap: 8px; }
.conv-row { display: flex; align-items: stretch; gap: 6px; }
.conv-item {
  flex: 1;
  display: block;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s;
  min-width: 0;
}
.conv-item:hover { border-color: #6366f1; }
.side-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-self: center;
}
.btn-hide {
  flex-shrink: 0;
  min-width: 46px;
  height: 32px;
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #64748b;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-hide:hover { border-color: #f87171; color: #f87171; background: #fef2f2; }
.btn-unhide {
  flex-shrink: 0;
  min-width: 46px;
  height: 32px;
  background: #eef2ff;
  border: 1px solid #6366f1;
  border-radius: 8px;
  color: #6366f1;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-unhide:hover { background: #e0e7ff; }
.btn-delete {
  flex-shrink: 0;
  min-width: 46px;
  height: 32px;
  background: #fff;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #ef4444;
  font-size: 0.75rem;
  cursor: pointer;
}
.btn-delete:hover { background: #fef2f2; }
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
.badge.jetbrains { background: #ede9fe; color: #5b21b6; }
.type-tag {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.68rem;
  font-weight: 500;
}
.type-api { background: #f3f4f6; color: #6b7280; }
.type-chat { background: #ecfdf5; color: #065f46; }
.type-code { background: #ede9fe; color: #5b21b6; }
.model { color: #6b7280; }
.cost { color: #059669; font-weight: 600; }
.tokens { color: #9ca3af; }
.conv-title { font-size: 0.9rem; color: #111; margin-bottom: 4px; }
.conv-stats { font-size: 0.75rem; color: #9ca3af; }
.empty { text-align: center; color: #aaa; font-size: 0.9rem; margin-top: 80px; }
.empty a { color: #6366f1; text-decoration: none; margin-left: 4px; }
</style>
