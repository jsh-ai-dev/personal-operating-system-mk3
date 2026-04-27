<!-- [페이지] /quiz/[id] — 특정 대화의 퀴즈 풀기 -->
<!-- 1문제씩 표시 → 선택 시 정답/오답 + 해설 즉시 공개 → 다음 → 최종 점수 -->

<script setup lang="ts">
import type { QuizQuestion } from '~/composables/useChat'

const route = useRoute()
const id = route.params.id as string

const { getConversation } = useChat()
const { data: conv, error } = await useAsyncData(`quiz-${id}`, () => getConversation(id))

// 퀴즈 데이터 — 페이지 진입 시점의 스냅샷으로 사용
const questions = computed<QuizQuestion[]>(() => conv.value?.quiz ?? [])

const current = ref(0)
const selected = ref<number | null>(null)   // 현재 문제에서 선택한 보기 인덱스
const revealed = ref(false)                  // 정답 보기 버튼으로 정답 공개 여부
const results = ref<boolean[]>([])           // 각 문제 정답 여부

const answered = computed(() => selected.value !== null || revealed.value)
const isCorrect = computed(() => {
  const q = questions.value[current.value]
  return selected.value !== null && q !== undefined && selected.value === q.answer
})
const finished = computed(() => results.value.length === questions.value.length && questions.value.length > 0)
const score = computed(() => results.value.filter(Boolean).length)

const selectOption = (idx: number) => {
  if (answered.value) return
  selected.value = idx
  results.value = [...results.value, idx === questions.value[current.value]?.answer]
}

const revealAnswer = () => {
  if (answered.value) return
  revealed.value = true
  // 정답 보기 = 스킵으로 간주 (오답 처리)
  results.value = [...results.value, false]
}

const next = () => {
  current.value += 1
  selected.value = null
  revealed.value = false
}

const restart = () => {
  current.value = 0
  selected.value = null
  results.value = []
}

const optionClass = (idx: number) => {
  if (!answered.value) return 'option'
  const q = questions.value[current.value]
  if (q === undefined) return 'option'
  if (idx === q.answer) return 'option correct'
  if (!revealed.value && idx === selected.value) return 'option wrong'
  return 'option dimmed'
}

const scoreLabel = computed(() => {
  const pct = Math.round((score.value / questions.value.length) * 100)
  if (pct === 100) return '완벽합니다!'
  if (pct >= 80) return '잘 하셨네요!'
  if (pct >= 60) return '절반 이상 맞았어요.'
  return '다시 도전해 보세요.'
})
</script>

<template>
  <main>
    <div v-if="error || !conv" class="empty">
      <p>대화를 불러올 수 없습니다.</p>
      <NuxtLink to="/quiz" class="btn-back">← 퀴즈 목록</NuxtLink>
    </div>

    <div v-else-if="!questions.length" class="empty">
      <p>아직 퀴즈가 없습니다.</p>
      <NuxtLink :to="`/quiz`" class="btn-back">← 퀴즈 목록에서 생성하기</NuxtLink>
    </div>

    <template v-else>
      <!-- 헤더 -->
      <header class="header">
        <NuxtLink to="/quiz" class="btn-back">← 목록</NuxtLink>
        <span class="conv-title">{{ conv.title }}</span>
        <span v-if="!finished" class="progress">{{ current + 1 }} / {{ questions.length }}</span>
      </header>

      <!-- 퀴즈 풀기 화면 -->
      <div v-show="!finished" class="quiz-box">
        <p class="question">{{ questions[current]?.question }}</p>

        <div class="options">
          <button
            v-for="(opt, idx) in questions[current]?.options"
            :key="idx"
            :class="optionClass(idx)"
            @click="selectOption(idx)"
          >
            {{ opt }}
          </button>
        </div>

        <!-- 답 선택 전: 정답 보기 버튼 -->
        <div v-show="!answered" class="reveal-row">
          <button class="btn-reveal" @click="revealAnswer">정답 보기</button>
        </div>

        <!-- 정답 공개 후 해설 + 다음 버튼 -->
        <div v-show="answered" class="feedback">
          <p v-show="!revealed" class="verdict" :class="isCorrect ? 'verdict-correct' : 'verdict-wrong'">
            {{ isCorrect ? '✓ 정답' : '✗ 오답' }}
          </p>
          <p class="explanation">{{ questions[current]?.explanation }}</p>
          <button v-if="current < questions.length - 1" class="btn-next" @click="next">
            다음 문제 →
          </button>
          <button v-else class="btn-next" @click="next">결과 보기 →</button>
        </div>
      </div>

      <!-- 최종 점수 화면 -->
      <div v-show="finished" class="result-box">
        <p class="score-num">{{ score }} / {{ questions.length }}</p>
        <p class="score-label">{{ scoreLabel }}</p>
        <div class="result-actions">
          <button class="btn-restart" @click="restart">다시 풀기</button>
          <NuxtLink to="/quiz" class="btn-list">퀴즈 목록</NuxtLink>
        </div>
      </div>
    </template>
  </main>
</template>

<style scoped>
main {
  max-width: 640px;
  margin: 40px auto;
  padding: 0 24px;
  font-family: monospace;
}
.header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 32px;
}
.btn-back {
  font-size: 0.82rem;
  color: #6b7280;
  text-decoration: none;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  white-space: nowrap;
}
.btn-back:hover { color: #374151; border-color: #9ca3af; }
.conv-title {
  font-size: 0.88rem;
  color: #374151;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.progress {
  font-size: 0.82rem;
  color: #9ca3af;
  white-space: nowrap;
}

/* 퀴즈 박스 */
.quiz-box { display: flex; flex-direction: column; gap: 20px; }
.question {
  font-size: 1rem;
  font-weight: 600;
  color: #111;
  line-height: 1.6;
  margin: 0;
}
.options { display: flex; flex-direction: column; gap: 10px; }
.option {
  text-align: left;
  font-family: monospace;
  font-size: 0.9rem;
  padding: 12px 16px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  cursor: pointer;
  transition: border-color 0.1s, background 0.1s;
  line-height: 1.5;
}
.option:hover:not(.correct):not(.wrong):not(.dimmed) {
  border-color: #6366f1;
  color: #4338ca;
}
.option.correct {
  border-color: #10b981;
  background: #ecfdf5;
  color: #065f46;
  cursor: default;
}
.option.wrong {
  border-color: #ef4444;
  background: #fef2f2;
  color: #991b1b;
  cursor: default;
}
.option.dimmed {
  opacity: 0.45;
  cursor: default;
}

/* 정답 보기 버튼 */
.reveal-row { display: flex; justify-content: flex-end; }
.btn-reveal {
  font-family: monospace;
  font-size: 0.82rem;
  padding: 6px 14px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #fff;
  color: #9ca3af;
  cursor: pointer;
}
.btn-reveal:hover { border-color: #9ca3af; color: #6b7280; }

/* 피드백 */
.feedback { display: flex; flex-direction: column; gap: 10px; }
.verdict { font-size: 0.95rem; font-weight: 700; margin: 0; }
.verdict-correct { color: #10b981; }
.verdict-wrong { color: #ef4444; }
.explanation {
  font-size: 0.85rem;
  color: #374151;
  line-height: 1.65;
  margin: 0;
  padding: 10px 14px;
  background: #f9fafb;
  border-radius: 6px;
  border-left: 3px solid #6366f1;
}
.btn-next {
  font-family: monospace;
  font-size: 0.88rem;
  padding: 9px 20px;
  background: #6366f1;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  align-self: flex-end;
}
.btn-next:hover { background: #4f46e5; }

/* 결과 화면 */
.result-box {
  text-align: center;
  margin-top: 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.score-num {
  font-size: 2.5rem;
  font-weight: 700;
  color: #111;
  margin: 0;
}
.score-label {
  font-size: 1rem;
  color: #6b7280;
  margin: 0;
}
.result-actions { display: flex; gap: 12px; margin-top: 16px; }
.btn-restart {
  font-family: monospace;
  font-size: 0.88rem;
  padding: 9px 20px;
  border: 1px solid #6366f1;
  border-radius: 8px;
  background: #fff;
  color: #6366f1;
  cursor: pointer;
}
.btn-restart:hover { background: #eef2ff; }
.btn-list {
  font-family: monospace;
  font-size: 0.88rem;
  padding: 9px 20px;
  background: #6366f1;
  color: #fff;
  border-radius: 8px;
  text-decoration: none;
}
.btn-list:hover { background: #4f46e5; }

/* 에러/빈 상태 */
.empty {
  text-align: center;
  color: #9ca3af;
  font-size: 0.9rem;
  margin-top: 80px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  align-items: center;
}
</style>
