<!-- [페이지] /chat — 전체 대화 목록 페이지. 각 항목 클릭 시 /chat/[id]로 이동 -->

<script setup lang="ts">
import type { ImportTarget, ImportUpload } from '~/composables/useChat'

const { listConversations, setHidden, deleteConversation, importJetbrainsCodex, importGeminiTakeout, importClaudeExport, importClaudeCode, importChatGptExport, uploadImportFiles, listImportUploads, deleteImportUpload } = useChat()

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
const importingChatGpt = ref(false)
const importResult = ref('')
const importModalOpen = ref(false)
const selectedImportKey = ref<ImportTarget>('jetbrains-codex')
const selectedFiles = ref<File[]>([])
const selectedUploadId = ref('')
const importUploads = ref<Partial<Record<ImportTarget, ImportUpload[]>>>({})
const uploadsLoading = ref(false)

const importOptions = [
  { label: 'ChatGPT', key: 'chatgpt-export', enabled: true },
  { label: 'Codex', key: 'jetbrains-codex', enabled: true },
  { label: 'Gemini', key: 'gemini-takeout', enabled: true },
  { label: 'Gemini Code Assist', key: 'gemini-code-assist', enabled: false },
  { label: 'Claude', key: 'claude-export', enabled: true },
  { label: 'Claude Code', key: 'claude-code', enabled: true },
  { label: 'Copilot', key: 'copilot', enabled: false },
  { label: 'Cursor', key: 'cursor', enabled: false },
] as const

// 서비스별 파일 선택 설정
const fileInputConfig = computed(() => {
  const configs: Record<string, { accept: string; multiple: boolean; hint: string }> = {
    'chatgpt-export': { accept: '.json', multiple: false, hint: 'conversations.json' },
    'claude-export':  { accept: '.json', multiple: false, hint: 'conversations.json' },
    'gemini-takeout': { accept: '.json', multiple: false, hint: '내활동.json' },
    'claude-code':    { accept: '.jsonl', multiple: true, hint: '*.jsonl 파일들' },
    'jetbrains-codex': { accept: '.events', multiple: true, hint: '*.events 파일들' },
  }
  return configs[selectedImportKey.value] ?? null
})

const onFileChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  selectedFiles.value = input.files ? Array.from(input.files) : []
  if (selectedFiles.value.length > 0) selectedUploadId.value = ''
}

const refreshImportUploads = async () => {
  uploadsLoading.value = true
  try {
    const uploads = await listImportUploads(selectedImportKey.value)
    importUploads.value[selectedImportKey.value] = uploads
    selectedUploadId.value = selectedUploadId.value && uploads.some(upload => upload.upload_id === selectedUploadId.value)
      ? selectedUploadId.value
      : uploads[0]?.upload_id ?? ''
  } catch {
    importUploads.value[selectedImportKey.value] = []
    selectedUploadId.value = ''
  } finally {
    uploadsLoading.value = false
  }
}

watch([importModalOpen, selectedImportKey], async ([open]) => {
  if (!open) return
  selectedFiles.value = []
  selectedUploadId.value = ''
  await refreshImportUploads()
})

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

const _runImport = async (fn: (uploadId?: string) => Promise<{ imported: number; skipped: number; total: number }>, setLoading: (v: boolean) => void, uploadId?: string) => {
  setLoading(true)
  importResult.value = ''
  try {
    const result = await fn(uploadId)
    importResult.value = result.imported > 0 ? `${result.imported}개 가져옴` : '이미 최신 상태'
    if (result.imported > 0) await refresh()
  } catch (e) {
    importResult.value = '오류 발생'
  } finally {
    setLoading(false)
    setTimeout(() => { importResult.value = '' }, 3000)
  }
}

const runImportCodex = (uploadId?: string) => _runImport(importJetbrainsCodex, v => { importingCodex.value = v }, uploadId)
const runImportGemini = (uploadId?: string) => _runImport(importGeminiTakeout, v => { importingGemini.value = v }, uploadId)
const runImportClaude = (uploadId?: string) => _runImport(importClaudeExport, v => { importingClaude.value = v }, uploadId)
const runImportClaudeCode = (uploadId?: string) => _runImport(importClaudeCode, v => { importingClaudeCode.value = v }, uploadId)
const runImportChatGpt = (uploadId?: string) => _runImport(importChatGptExport, v => { importingChatGpt.value = v }, uploadId)

const isImporting = computed(() => importingCodex.value || importingGemini.value || importingClaude.value || importingClaudeCode.value || importingChatGpt.value)

const runImportByKey = async () => {
  let uploadId: string | undefined
  // 파일이 선택돼 있으면 S3 업로드 먼저
  if (selectedFiles.value.length > 0) {
    try {
      const upload = await uploadImportFiles(selectedImportKey.value, selectedFiles.value)
      uploadId = upload.upload_id
    } catch {
      importResult.value = '업로드 실패'
      setTimeout(() => { importResult.value = '' }, 3000)
      importModalOpen.value = false
      selectedFiles.value = []
      return
    }
  } else if (selectedUploadId.value) {
    uploadId = selectedUploadId.value
  } else {
    importResult.value = '가져올 업로드 파일을 선택하세요'
    setTimeout(() => { importResult.value = '' }, 3000)
    return
  }

  importModalOpen.value = false
  selectedFiles.value = []

  if (selectedImportKey.value === 'jetbrains-codex') await runImportCodex(uploadId)
  if (selectedImportKey.value === 'claude-export') await runImportClaude(uploadId)
  if (selectedImportKey.value === 'claude-code') await runImportClaudeCode(uploadId)
  if (selectedImportKey.value === 'gemini-takeout') await runImportGemini(uploadId)
  if (selectedImportKey.value === 'chatgpt-export') await runImportChatGpt(uploadId)
}

const removeImportUpload = async (upload: ImportUpload) => {
  if (!confirm('업로드 원본 파일을 S3에서 삭제할까요?')) return
  try {
    await deleteImportUpload(selectedImportKey.value, upload.upload_id)
    importUploads.value[selectedImportKey.value] = (importUploads.value[selectedImportKey.value] ?? [])
      .filter(item => item.upload_id !== upload.upload_id)
    if (selectedUploadId.value === upload.upload_id) selectedUploadId.value = ''
    importResult.value = '업로드 파일 삭제 완료'
  } catch {
    importResult.value = '업로드 파일 삭제 실패'
  } finally {
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
    'codex': 'Codex',
    'claude-code': 'Claude Code',
    'claude': 'Claude',
    'gemini': 'Gemini',
    'chatgpt': 'ChatGPT',
  }
  if (labels[conv.model]) return labels[conv.model]
  return ({ openai: 'OpenAI', anthropic: 'Claude API', google: 'Gemini API' })[conv.provider] ?? conv.provider
}

// 대화 타입 — API(직접 호출) / 채팅 임포트(구독 서비스) / 코딩 임포트(코딩 어시스턴트)
const convType = (conv: { model: string }): { label: string; cls: string } => {
  if (conv.model === 'codex' || conv.model === 'claude-code')
    return { label: '코딩', cls: 'type-code' }
  if (conv.model === 'claude' || conv.model === 'gemini' || conv.model === 'chatgpt')
    return { label: '채팅 임포트', cls: 'type-chat' }
  return { label: 'API', cls: 'type-api' }
}

const convFilterKey = (conv: { provider: string; model: string }): FilterKey => {
  if (conv.model === 'codex') return 'jetbrains-codex'
  if (conv.model === 'claude-code') return 'claude-code'
  if (conv.model === 'claude') return 'claude-export'
  if (conv.model === 'gemini') return 'gemini-takeout'
  if (conv.model === 'chatgpt') return 'chatgpt'
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

const currentUploads = computed(() => importUploads.value[selectedImportKey.value] ?? [])
</script>

<template>
  <main>
    <header class="header">
      <h1>AI Chat</h1>
      <div class="header-actions">
        <button class="btn-toggle-hidden" :class="{ active: showHidden }" @click="toggleShowHidden">
          {{ showHidden ? '완료' : '숨김 관리' }}
        </button>
        <button class="btn-import" :disabled="isImporting" @click="importModalOpen = true">
          내역 가져오기
        </button>
        <span v-if="importResult" class="import-result">{{ importResult }}</span>
        <NuxtLink to="/chat/new" class="btn-new">+ 새 대화</NuxtLink>
      </div>
    </header>
    <div v-if="importModalOpen" class="modal-overlay">
      <div class="modal">
        <p class="modal-title">내역 가져오기</p>
        <select v-model="selectedImportKey" class="modal-select" :disabled="isImporting" @change="selectedFiles = []; selectedUploadId = ''">
          <option v-for="opt in importOptions" :key="opt.key" :value="opt.key" :disabled="!opt.enabled">
            {{ opt.label }} {{ opt.enabled ? '' : '(준비 중...)' }}
          </option>
        </select>
        <div v-if="fileInputConfig" class="file-input-wrap">
          <label class="file-label">
            <span class="file-hint">{{ fileInputConfig.hint }}</span>
            <input
              class="file-input"
              type="file"
              :accept="fileInputConfig.accept"
              :multiple="fileInputConfig.multiple"
              :disabled="isImporting"
              @change="onFileChange"
            >
          </label>
          <span v-if="selectedFiles.length > 0" class="file-count">{{ selectedFiles.length }}개 선택됨</span>
        </div>
        <div class="upload-list-header">
          <span>업로드된 파일</span>
          <span v-if="uploadsLoading" class="upload-list-meta">불러오는 중</span>
        </div>
        <div class="upload-list">
          <label
            v-for="upload in currentUploads"
            :key="upload.upload_id"
            class="upload-item"
            :class="{ selected: selectedUploadId === upload.upload_id }"
          >
            <input
              v-model="selectedUploadId"
              type="radio"
              name="import-upload"
              :value="upload.upload_id"
              :disabled="isImporting || selectedFiles.length > 0"
            >
            <span class="upload-item-body">
              <span class="upload-item-title">
                {{ upload.filenames.length === 1 ? upload.filenames[0] : `${upload.file_count}개 파일` }}
              </span>
              <span class="upload-item-meta">
                업로드 {{ new Date(upload.created_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}
                <template v-if="upload.imported_at">
                  · 가져오기 {{ new Date(upload.imported_at).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }}
                </template>
              </span>
            </span>
            <button class="upload-delete-btn" :disabled="isImporting" @click.prevent.stop="removeImportUpload(upload)">삭제</button>
          </label>
          <p v-if="currentUploads.length === 0" class="upload-empty">아직 업로드된 파일이 없습니다.</p>
        </div>
        <div class="modal-actions">
          <button class="btn-import" @click="importModalOpen = false; selectedFiles = []">취소</button>
          <button class="btn-import" :disabled="isImporting || !importOptions.find(v => v.key === selectedImportKey)?.enabled || (selectedFiles.length === 0 && !selectedUploadId)" @click="runImportByKey">
            {{ selectedFiles.length > 0 ? '업로드 & 가져오기' : '가져오기' }}
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
            <template v-if="convType(conv).label === 'API'">
              <span class="model">{{ conv.model }}</span>
              <span class="cost">{{ formatCost(conv.total_cost_usd) }}</span>
            </template>
          </div>
          <div class="conv-title">{{ conv.title }}</div>
          <div class="conv-stats">
            메시지 {{ conv.message_count }}개 · 생성 {{ formatDate(conv.created_at) }}
          </div>
        </NuxtLink>
        <button v-if="showHidden" class="btn-eye" :class="{ 'btn-eye-hidden': conv.is_hidden }" @click="conv.is_hidden ? unhide($event, conv.id) : hide($event, conv.id)" :title="conv.is_hidden ? '숨김 해제' : '숨기기'">
          <svg v-if="conv.is_hidden" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
            <line x1="1" y1="1" x2="23" y2="23"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
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
  width: min(520px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow-y: auto;
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
.file-input-wrap { margin-top: 8px; display: flex; align-items: center; gap: 8px; }
.file-label { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.file-hint { font-size: 0.72rem; color: #9ca3af; }
.file-input { font-family: monospace; font-size: 0.78rem; width: 100%; }
.file-count { font-size: 0.75rem; color: #059669; white-space: nowrap; }
.upload-list-header {
  display: flex;
  justify-content: space-between;
  margin: 10px 0 6px;
  font-size: 0.76rem;
  font-weight: 700;
  color: #374151;
}
.upload-list-meta {
  font-weight: 400;
  color: #9ca3af;
}
.upload-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
}
.upload-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
}
.upload-item.selected {
  border-color: #6366f1;
  background: #eef2ff;
}
.upload-item-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.upload-item-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.76rem;
  font-weight: 700;
  color: #111827;
}
.upload-item-meta {
  font-size: 0.7rem;
  color: #6b7280;
}
.upload-delete-btn {
  padding: 4px 7px;
  border: 1px solid #fecaca;
  border-radius: 6px;
  background: #fff;
  color: #dc2626;
  font-family: monospace;
  font-size: 0.7rem;
  cursor: pointer;
}
.upload-delete-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
.upload-empty {
  margin: 0;
  padding: 10px;
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  color: #9ca3af;
  font-size: 0.76rem;
}
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
.conv-row { position: relative; }
.conv-item {
  display: block;
  padding: 14px 44px 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s;
}
.conv-item:hover { border-color: #6366f1; }
.btn-eye {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #cbd5e1;
  cursor: pointer;
  z-index: 1;
  transition: color 0.15s;
}
.btn-eye:hover { color: #94a3b8; }
.btn-eye-hidden { color: #6366f1; }
.btn-eye-hidden:hover { color: #4f46e5; }
/* 숨긴 항목은 흐리게 표시 */
.conv-row:has(.btn-eye-hidden) .conv-item { opacity: 0.45; }
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
  line-height: 1;
  background: #f3f4f6;
  color: #374151;
}
.badge.openai { background: #d1fae5; color: #065f46; }
.badge.anthropic { background: #fde68a; color: #78350f; }
.badge.google { background: #dbeafe; color: #1e3a8a; }
.badge.jetbrains { background: #d1fae5; color: #065f46; }
.type-tag {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.68rem;
  font-weight: 500;
  line-height: 1;
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
