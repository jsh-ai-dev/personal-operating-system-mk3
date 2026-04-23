// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },  // 개발 중 Nuxt DevTools 패널 활성화

  devServer: {
    port: 3003,  // 기본 포트(3000)에서 변경 (mk1, mk2와 포트 충돌 방지)
  },

  // runtimeConfig: 환경변수를 Nuxt 앱 안에서 사용할 수 있게 등록
  // public 하위 값은 서버/클라이언트(브라우저) 양쪽 모두 접근 가능
  // public 외부 값은 서버 사이드에서만 접근 가능 (시크릿 보호용)
  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:8001',  // 백엔드 API 기본 주소
    },
  },
})
