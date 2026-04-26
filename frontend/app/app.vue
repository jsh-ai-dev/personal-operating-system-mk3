<!-- [레이아웃] 전체 앱의 루트 컴포넌트 — 좌측 사이드바 + 우측 콘텐츠 구조 -->
<!-- NuxtPage가 현재 URL에 맞는 pages/ 하위 컴포넌트를 자동으로 렌더링 -->

<template>
  <div class="layout">
    <NuxtRouteAnnouncer />

    <nav class="sidebar">
      <div class="logo">POS mk3</div>
      <NuxtLink to="/" class="nav-link">대시보드</NuxtLink>
      <NuxtLink to="/chat" class="nav-link">AI Chat</NuxtLink>
    </nav>

    <div class="content">
      <NuxtPage />
    </div>
  </div>
</template>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; }
</style>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
}
.sidebar {
  width: 160px;
  flex-shrink: 0;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  padding: 20px 0;
  font-family: monospace;
}
.logo {
  font-size: 0.8rem;
  font-weight: 700;
  color: #6366f1;
  padding: 0 16px 20px;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 8px;
}
.nav-link {
  display: block;
  padding: 8px 16px;
  font-size: 0.85rem;
  color: #6b7280;
  text-decoration: none;
  border-radius: 0;
  transition: background 0.1s;
}
.nav-link:hover { background: #f3f4f6; color: #111; }
.nav-link.router-link-active { color: #6366f1; background: #eef2ff; font-weight: 600; }
.content {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}
</style>
