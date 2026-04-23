// useApi: 앱 전체에서 공통으로 사용할 API 클라이언트를 반환하는 컴포저블
// baseURL을 runtimeConfig에서 읽어 모든 요청에 자동으로 붙여줌
// 사용 예: const api = useApi()  →  api('/api/v1/health')
export const useApi = () => {
  const config = useRuntimeConfig()
  return $fetch.create({ baseURL: config.public.apiBase })
}
