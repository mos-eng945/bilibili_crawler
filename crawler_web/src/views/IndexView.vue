<script setup>
import { computed, ref } from 'vue'
import {
  BookOpen,
  ChartNoAxesCombined,
  ChartSpline,
  ChevronDown,
  Download,
  FileText,
  Search,
  Settings,
  Upload,
  UserRound,
} from '@lucide/vue'

const SIDEBAR_WIDTH_KEY = 'crawler-web-sidebar-width'
const ICON_MIN_WIDTH = 72
const LABEL_HIDE_WIDTH = 180
const MAX_SIDEBAR_WIDTH = 380
const DEFAULT_SIDEBAR_WIDTH = 232

const navigation = [
  { label: '项目介绍', to: '/project', icon: BookOpen },
  { label: '数据概览', to: '/overview', icon: ChartNoAxesCombined },
  { label: '数据分析', to: '/analysis', icon: ChartSpline },
  { label: '搜索历史', to: '/history', icon: Search },
  { label: '报告', to: '/reports', icon: FileText },
  { label: '设置', to: '/settings', icon: Settings },
]

function readSidebarWidth() {
  const storedValue = localStorage.getItem(SIDEBAR_WIDTH_KEY)
  if (storedValue === null) return DEFAULT_SIDEBAR_WIDTH

  const storedWidth = Number(storedValue)
  if (!Number.isFinite(storedWidth)) return DEFAULT_SIDEBAR_WIDTH
  if (storedWidth <= 0) return 0
  if (storedWidth < ICON_MIN_WIDTH) return 0
  if (storedWidth > MAX_SIDEBAR_WIDTH) return MAX_SIDEBAR_WIDTH
  return storedWidth
}

function clampSidebarWidth(value) {
  if (value < ICON_MIN_WIDTH) return 0
  if (value > MAX_SIDEBAR_WIDTH) return MAX_SIDEBAR_WIDTH
  return value
}

const sidebarWidth = ref(readSidebarWidth())
const resizing = ref(false)

const sidebarHidden = computed(() => sidebarWidth.value === 0)
const sidebarIconOnly = computed(() => {
  if (sidebarWidth.value === 0) return false
  return sidebarWidth.value < LABEL_HIDE_WIDTH
})

function startSidebarResize(event) {
  event.preventDefault()

  const startX = event.clientX
  const startWidth = sidebarWidth.value
  resizing.value = true

  function handlePointerMove(moveEvent) {
    const nextWidth = startWidth + moveEvent.clientX - startX
    sidebarWidth.value = clampSidebarWidth(nextWidth)
  }

  function handlePointerEnd() {
    resizing.value = false
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', handlePointerEnd)
    window.removeEventListener('pointercancel', handlePointerEnd)
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(Math.round(sidebarWidth.value)))
  }

  window.addEventListener('pointermove', handlePointerMove)
  window.addEventListener('pointerup', handlePointerEnd)
  window.addEventListener('pointercancel', handlePointerEnd)
}

function handleSidebarResizeKeydown(event) {
  if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
  event.preventDefault()

  let delta = 16
  if (event.key === 'ArrowLeft') delta = -16

  sidebarWidth.value = clampSidebarWidth(sidebarWidth.value + delta)
  localStorage.setItem(SIDEBAR_WIDTH_KEY, String(Math.round(sidebarWidth.value)))
}

</script>

<template>
  <div class="index" :class="{ 'is-resizing': resizing }">
    <header class="topbar">
      <RouterLink class="brand" to="/overview">
        <img class="brand__mark" src="@/assets/brand.svg" alt="" width="34" height="34" />
        <div class="brand__text">
          <strong>Bilibili 数据分析台</strong>
          <span>Analysis workspace</span>
        </div>
      </RouterLink>

      <RouterLink class="account" active-class="is-active" to="/user">
        <UserRound :size="16" aria-hidden="true" />
        <span>账号</span>
        <ChevronDown :size="14" aria-hidden="true" />
      </RouterLink>
    </header>

    <div
      class="layout"
      :class="{ 'is-hidden': sidebarHidden, 'is-icon-only': sidebarIconOnly }"
      :style="{ '--sidebar-width': sidebarWidth + 'px' }"
    >
      <aside class="sidebar">
        <nav class="nav" aria-label="功能导航">
          <RouterLink
            v-for="item in navigation"
            :key="item.to"
            class="nav__item"
            active-class="is-active"
            :aria-label="item.label"
            :title="item.label"
            :to="item.to"
          >
            <component :is="item.icon" :size="18" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>

        <div
          class="sidebar-resizer"
          role="separator"
          aria-label="调整侧栏宽度"
          aria-orientation="vertical"
          aria-valuemin="0"
          :aria-valuemax="MAX_SIDEBAR_WIDTH"
          :aria-valuenow="sidebarWidth"
          tabindex="0"
          @pointerdown="startSidebarResize"
          @keydown="handleSidebarResizeKeydown"
        ></div>
      </aside>

      <main class="content">
        <RouterView />
      </main>
    </div>

    <div class="data-actions" aria-label="数据操作">
      <RouterLink class="action-button action-button--primary" to="/import">
        <Upload :size="16" aria-hidden="true" />
        <span>导入数据</span>
      </RouterLink>
      <RouterLink class="action-button action-button--secondary" to="/export">
        <Download :size="16" aria-hidden="true" />
        <span>导出结果</span>
      </RouterLink>
    </div>
  </div>
</template>

<style scoped>
.index {
  --index-bg: #f4f5f7;
  --index-panel: #ffffff;
  --index-surface: #ffffff;
  --index-surface-hover: #f1f2f4;
  --index-border: #e3e5e9;
  --index-border-strong: #ccd1d8;
  --index-text: #1b1d22;
  --index-muted: #626771;
  --index-faint: #949aa3;
  --index-accent: #fb7299;
  --index-accent-strong: #e75a84;
  --index-accent-soft: #fdeef4;

  min-height: 100%;
  color: var(--index-text);
  background: var(--index-bg);
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: var(--index-panel);
  border-bottom: 1px solid var(--index-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
  color: inherit;
  text-decoration: none;
}

.brand__mark {
  display: block;
  flex: none;
}

.brand__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand__text strong {
  overflow: hidden;
  color: var(--index-text);
  font-size: 14px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand__text span {
  color: var(--index-faint);
  font-size: 10px;
  line-height: 1.3;
}

.account {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 13px;
  color: var(--index-muted);
  text-decoration: none;
  background: var(--index-surface);
  border: 1px solid var(--index-border);
  border-radius: 999px;
  cursor: pointer;
  transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease;
}

.account:hover {
  color: var(--index-text);
  background: var(--index-surface-hover);
  border-color: var(--index-border-strong);
}

.account.is-active {
  color: var(--index-text);
  background: var(--index-accent-soft);
  border-color: var(--index-accent-soft);
}

.layout {
  display: grid;
  grid-template-columns: var(--sidebar-width, 232px) minmax(0, 1fr);
  min-height: calc(100vh - 64px);
  transition: grid-template-columns 0.2s ease;
}

.index.is-resizing {
  cursor: col-resize;
  user-select: none;
}

.index.is-resizing .layout {
  transition: none;
}

.sidebar {
  position: sticky;
  top: 64px;
  z-index: 10;
  align-self: start;
  height: calc(100vh - 64px);
  min-width: 0;
  padding: 22px 14px;
  overflow: visible;
  background: var(--index-panel);
  border-right: 1px solid var(--index-border);
  transition: opacity 0.16s ease, padding 0.2s ease, border-color 0.2s ease;
}

.layout.is-hidden .sidebar {
  padding: 0;
}

.layout.is-hidden .nav {
  visibility: hidden;
  opacity: 0;
  pointer-events: none;
}

.layout.is-hidden .sidebar-resizer {
  right: -8px;
}

.layout.is-icon-only .sidebar {
  padding-right: 10px;
  padding-left: 10px;
}

.layout.is-icon-only .nav__item {
  justify-content: center;
  gap: 0;
  padding: 0;
}

.layout.is-icon-only .nav__item span {
  display: none;
}

.layout.is-icon-only .nav__item.is-active::before {
  top: auto;
  right: auto;
  bottom: 5px;
  left: 50%;
  width: 16px;
  height: 2px;
  transform: translateX(-50%);
}

.sidebar-resizer {
  position: absolute;
  top: 0;
  right: -4px;
  z-index: 8;
  width: 8px;
  height: 100%;
  cursor: col-resize;
  touch-action: none;
}

.sidebar-resizer::before {
  position: absolute;
  top: 20px;
  left: 2px;
  width: 4px;
  height: 58px;
  background: var(--index-border-strong);
  border-radius: 999px;
  content: '';
  transition: background-color 0.15s ease;
}

.sidebar-resizer:hover::before,
.sidebar-resizer:focus-visible::before {
  background: var(--index-accent);
}

.sidebar-resizer:focus-visible {
  outline: none;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  height: 42px;
  padding: 0 12px;
  color: var(--index-muted);
  text-decoration: none;
  border-radius: 6px;
  transition: color 0.15s ease, background-color 0.15s ease;
}

.nav__item:hover {
  color: var(--index-text);
  background: var(--index-surface-hover);
}

.nav__item.is-active {
  color: var(--index-text);
  background: var(--index-accent-soft);
}

.nav__item.is-active::before {
  position: absolute;
  top: 13px;
  left: 0;
  width: 2px;
  height: 16px;
  background: var(--index-accent);
  border-radius: 2px;
  content: '';
}

.nav__item span {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content {
  width: 100%;
  max-width: 1240px;
  min-width: 0;
  padding: 58px 48px 128px;
}

.data-actions {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 30;
  display: flex;
  gap: 8px;
  padding: 8px;
  background: var(--index-panel);
  border: 1px solid var(--index-border);
  border-radius: 10px;
  box-shadow: 0 14px 36px rgba(27, 29, 34, 0.14);
}

.action-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  padding: 0 15px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
}

.action-button--primary {
  color: #ffffff;
  background: var(--index-accent);
  border: 1px solid var(--index-accent);
}

.action-button--primary:hover {
  background: var(--index-accent-strong);
  border-color: var(--index-accent-strong);
}

.action-button--secondary {
  color: var(--index-text);
  background: var(--index-surface);
  border: 1px solid var(--index-border);
}

.action-button--secondary:hover {
  background: var(--index-surface-hover);
  border-color: var(--index-border-strong);
}

@media (max-width: 1024px) {
  .content {
    padding: 46px 34px 120px;
  }
}

@media (max-width: 760px) {
  .topbar {
    height: 58px;
    padding: 0 16px;
  }

  .brand__text span {
    display: none;
  }

  .layout {
    display: block;
    min-height: calc(100vh - 58px);
  }

  .sidebar-resizer {
    display: none;
  }

  .sidebar {
    position: sticky;
    top: 58px;
    z-index: 15;
    width: 100%;
    height: auto;
    padding: 8px;
    overflow-x: auto;
    background: var(--index-panel);
    border-right: 0;
    border-bottom: 1px solid var(--index-border);
  }

  .nav {
    flex-direction: row;
    width: max-content;
  }

  .nav__item {
    width: auto;
    padding: 0 12px;
  }

  .nav__item.is-active::before {
    top: auto;
    right: 12px;
    bottom: 0;
    left: 12px;
    width: auto;
    height: 2px;
  }

  .content {
    padding: 34px 18px 112px;
  }

  .data-actions {
    right: 16px;
    bottom: 16px;
  }
}

@media (max-width: 480px) {
  .account {
    width: 36px;
    padding: 0;
    justify-content: center;
  }

  .account span,
  .account svg:last-child {
    display: none;
  }

  .content {
    padding-top: 28px;
  }

  .data-actions {
    left: 16px;
    right: 16px;
  }

  .action-button {
    flex: 1;
    padding: 0 12px;
  }
}
</style>
