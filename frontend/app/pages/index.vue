<!-- [대시보드] 등록된 AI 서비스 목록과 월 구독료 합계를 보여주는 메인 페이지 -->
<!-- AiServiceCard 컴포넌트를 그리드로 나열하고 서비스 추가 버튼을 제공함 -->

<script setup lang="ts">
import type { AIService } from '~/composables/useAiServices'

const { list, syncClaude, syncChatGPT, syncCodex, syncGemini, syncCursor } = useAiServices()

// 전체 AI 서비스 목록 로드 (DB에 저장된 마지막 데이터 즉시 표시)
const { data: services, refresh } = await useAsyncData('ai-services', list)

// 같은 구독을 공유하는 그룹 — 그룹당 첫 번째 항목만 합계에 포함
const SUBSCRIPTION_GROUPS = [
  ['ChatGPT', 'Codex'],
  ['Claude', 'Claude Code'],
]

function deduplicateBySubscription(list: AIService[]): AIService[] {
  const counted = new Set<number>()
  return list.filter((s) => {
    const groupIdx = SUBSCRIPTION_GROUPS.findIndex(g => g.includes(s.name ?? ''))
    if (groupIdx === -1) return true
    if (counted.has(groupIdx)) return false
    counted.add(groupIdx)
    return true
  })
}

const totalUSD = computed(() =>
  deduplicateBySubscription(services.value ?? [])
    .filter((s: AIService) => s.currency === 'USD' && s.monthly_cost != null)
    .reduce((sum: number, s: AIService) => sum + s.monthly_cost!, 0)
)

const totalKRW = computed(() =>
  deduplicateBySubscription(services.value ?? [])
    .filter((s: AIService) => s.currency === 'KRW' && s.monthly_cost != null)
    .reduce((sum: number, s: AIService) => sum + s.monthly_cost!, 0)
)

type SyncStatus = 'idle' | 'syncing' | 'done' | 'login_required' | 'error'

const claudeSyncStatus = ref<SyncStatus>('idle')
const chatgptSyncStatus = ref<SyncStatus>('idle')
const codexSyncStatus = ref<SyncStatus>('idle')
const geminiSyncStatus = ref<SyncStatus>('idle')
const cursorSyncStatus = ref<SyncStatus>('idle')

const runChatGPTSync = async () => {
  chatgptSyncStatus.value = 'syncing'
  try {
    const result: any = await syncChatGPT()
    if (result?.login_required) {
      chatgptSyncStatus.value = 'login_required'
    } else {
      await refresh()
      chatgptSyncStatus.value = 'done'
    }
  } catch {
    chatgptSyncStatus.value = 'error'
  }
}

const runCodexSync = async () => {
  codexSyncStatus.value = 'syncing'
  try {
    const result: any = await syncCodex()
    if (result?.login_required) {
      codexSyncStatus.value = 'login_required'
    } else {
      await refresh()
      codexSyncStatus.value = 'done'
    }
  } catch {
    codexSyncStatus.value = 'error'
  }
}

const runGeminiSync = async () => {
  geminiSyncStatus.value = 'syncing'
  try {
    const result: any = await syncGemini()
    if (result?.login_required) {
      geminiSyncStatus.value = 'login_required'
    } else {
      await refresh()
      geminiSyncStatus.value = 'done'
    }
  } catch {
    geminiSyncStatus.value = 'error'
  }
}

const runCursorSync = async () => {
  cursorSyncStatus.value = 'syncing'
  try {
    const result: any = await syncCursor()
    if (result?.login_required) {
      cursorSyncStatus.value = 'login_required'
    } else {
      await refresh()
      cursorSyncStatus.value = 'done'
    }
  } catch {
    cursorSyncStatus.value = 'error'
  }
}

// 저장된 next_billing_date가 오늘 이하면 결제일이 지난 것
const isBillingPast = (name: string) => {
  const service = (services.value ?? []).find((s: AIService) => s.name === name)
  if (!service?.next_billing_date) return false
  const nextBilling = new Date(service.next_billing_date)
  nextBilling.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return nextBilling <= today
}

const isRefreshing = ref(false)

// 새로고침 버튼 클릭 시 실행 — 같은 Chrome CDP 세션 공유로 순차 실행
const runAllSync = async () => {
  if (isRefreshing.value) return
  isRefreshing.value = true

  const hasCodex = (services.value ?? []).some((s: AIService) => s.name === 'Codex')
  const hasClaude = (services.value ?? []).some((s: AIService) => s.name === 'Claude')

  if (hasCodex) {
    codexSyncStatus.value = 'syncing'
    try {
      const result: any = await syncCodex()
      codexSyncStatus.value = result?.login_required ? 'login_required' : 'done'
    } catch {
      codexSyncStatus.value = 'error'
    }
  }

  if (hasClaude) {
    claudeSyncStatus.value = 'syncing'
    try {
      const result: any = await syncClaude()
      claudeSyncStatus.value = result?.login_required ? 'login_required' : 'done'
    } catch {
      claudeSyncStatus.value = 'error'
    }
  }

  await refresh()

  // ChatGPT는 결제일이 지난 경우에만 갱신
  if (isBillingPast('ChatGPT')) {
    await runChatGPTSync()
  }

  isRefreshing.value = false
}

const handleDeleted = async () => {
  await refresh()
}
</script>

<template>
  <main>
    <header class="header">
      <h1>AI 서비스 현황</h1>
      <div class="header-actions">
        <button class="btn-refresh" :disabled="isRefreshing" @click="runAllSync">
          {{ isRefreshing ? '갱신 중...' : '↻ 새로고침' }}
        </button>
        <NuxtLink to="/ai-services/new" class="btn-add">+ 추가</NuxtLink>
      </div>
    </header>

    <!-- 총 구독료 요약 -->
    <div class="summary">
      <div v-if="totalUSD > 0" class="summary-item">
        <span>USD 합계</span>
        <strong>${{ totalUSD.toFixed(2) }}</strong>
      </div>
      <div v-if="totalKRW > 0" class="summary-item">
        <span>KRW 합계</span>
        <strong>₩{{ totalKRW.toLocaleString() }}</strong>
      </div>
      <span class="count">{{ services?.length ?? 0 }}개 서비스</span>

      <!-- 갱신 상태 표시 -->
      <span v-if="codexSyncStatus === 'syncing'" class="sync-status syncing">Codex 갱신 중...</span>
      <span v-else-if="codexSyncStatus === 'done'" class="sync-status done">Codex ✓</span>
      <span v-else-if="codexSyncStatus === 'login_required'" class="sync-status warn">Codex 로그인 필요</span>
      <span v-else-if="codexSyncStatus === 'error'" class="sync-status error">Codex 갱신 실패</span>

      <span v-if="claudeSyncStatus === 'syncing'" class="sync-status syncing">Claude 갱신 중...</span>
      <span v-else-if="claudeSyncStatus === 'done'" class="sync-status done">Claude ✓</span>
      <span v-else-if="claudeSyncStatus === 'login_required'" class="sync-status warn">Claude 로그인 필요</span>
      <span v-else-if="claudeSyncStatus === 'error'" class="sync-status error">Claude 갱신 실패</span>

      <span v-if="chatgptSyncStatus === 'syncing'" class="sync-status syncing">ChatGPT 갱신 중...</span>
      <span v-else-if="chatgptSyncStatus === 'done'" class="sync-status done">ChatGPT ✓</span>
      <span v-else-if="chatgptSyncStatus === 'login_required'" class="sync-status warn">ChatGPT 로그인 필요</span>
      <span v-else-if="chatgptSyncStatus === 'error'" class="sync-status error">ChatGPT 갱신 실패</span>
    </div>

    <!-- 서비스 카드 목록 -->
    <div v-if="services?.length" class="cards">
      <AiServiceCard
        v-for="service in services"
        :key="service.id"
        :service="service"
        :sync-status="service.name === 'ChatGPT' ? chatgptSyncStatus : service.name === 'Gemini' ? geminiSyncStatus : undefined"
        @deleted="handleDeleted"
        @sync="service.name === 'ChatGPT' ? runChatGPTSync() : service.name === 'Gemini' ? runGeminiSync() : undefined"
      />
    </div>

    <div v-else class="empty">
      등록된 AI 서비스가 없습니다.
      <NuxtLink to="/ai-services/new">추가하기 →</NuxtLink>
    </div>
  </main>
</template>

<style scoped>
main {
  max-width: 960px;
  margin: 40px auto;
  padding: 0 24px;
  font-family: monospace;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
h1 { font-size: 1.3rem; }
.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.btn-refresh {
  padding: 6px 14px;
  border: 1px solid #94a3b8;
  border-radius: 6px;
  color: #64748b;
  background: none;
  cursor: pointer;
  font-size: 0.85rem;
  font-family: monospace;
}
.btn-refresh:hover:not(:disabled) { background: #f1f5f9; }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-add {
  padding: 6px 14px;
  border: 1px solid #6366f1;
  border-radius: 6px;
  color: #6366f1;
  text-decoration: none;
  font-size: 0.85rem;
  font-family: monospace;
}
.btn-add:hover { background: #eef2ff; }
.summary {
  display: flex;
  align-items: baseline;
  gap: 20px;
  margin-bottom: 28px;
  font-size: 0.85rem;
  color: #666;
}
.summary-item { display: flex; align-items: baseline; gap: 8px; }
.summary-item strong { font-size: 1.4rem; color: #111; }
.count { color: #aaa; }
.sync-status { font-size: 0.75rem; }
.sync-status.syncing { color: #f59e0b; }
.sync-status.done { color: #22c55e; }
.sync-status.warn { color: #f59e0b; }
.sync-status.error { color: #ef4444; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.empty { color: #aaa; font-size: 0.9rem; margin-top: 60px; text-align: center; }
.empty a { color: #6366f1; text-decoration: none; margin-left: 4px; }
</style>
