// [API 클라이언트] 앱 전체에서 공통으로 사용할 HTTP 클라이언트를 반환하는 컴포저블

// useApi: 앱 전체에서 공통으로 사용할 API 클라이언트를 반환하는 컴포저블
// baseURL을 runtimeConfig에서 읽어 모든 요청에 자동으로 붙여줌
// 사용 예: const api = useApi()  →  api('/api/v1/health')
export const useApi = () => {
  const config = useRuntimeConfig()
  const baseURL = process.server ? config.apiBaseServer : config.public.apiBase
  const forwardedHeaders = process.server ? useRequestHeaders(['cookie']) : undefined
  // mk2 로그인 쿠키(pos_session)를 함께 보내야 mk3 backend에서 인증 가능
  return $fetch.create({
    baseURL,
    credentials: 'include',
    headers: forwardedHeaders,
  })
}
