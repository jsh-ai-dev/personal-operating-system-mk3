<!-- [루트 컴포넌트] Nuxt 앱의 최상위 컴포넌트 — 모든 페이지를 감싸는 껍데기 역할 -->

<template>
  <!-- 앱의 루트 컴포넌트 -->
  <div>
    <NuxtRouteAnnouncer />  <!-- 스크린 리더를 위한 페이지 전환 알림 -->
    <NuxtPage />            <!-- 현재 URL에 해당하는 pages/ 컴포넌트를 렌더링 -->
  </div>
</template>
