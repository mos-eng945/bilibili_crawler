<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronDown,
  ChevronRight,
  LogOut,
  UserRound,
} from '@lucide/vue'

import { signOut } from '@/auth'

const accountOpen = ref(false)
const accountMenu = ref(null)
const accountButton = ref(null)
const router = useRouter()

function closeAccountMenu(restoreFocus = false) {
  accountOpen.value = false
  if (restoreFocus) accountButton.value?.focus()
}

function handleAccountPointerDown(event) {
  if (accountMenu.value && !accountMenu.value.contains(event.target)) {
    closeAccountMenu()
  }
}

function handleAccountKeydown(event) {
  if (event.key === 'Escape' && accountOpen.value) {
    closeAccountMenu(true)
  }
}

function handleSignOut() {
  closeAccountMenu()
  signOut()
  router.replace('/login')
}

onMounted(() => {
  document.addEventListener('pointerdown', handleAccountPointerDown)
  document.addEventListener('keydown', handleAccountKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleAccountPointerDown)
  document.removeEventListener('keydown', handleAccountKeydown)
})
</script>

<template>
  <div ref="accountMenu" class="account-menu">
    <button
      ref="accountButton"
      class="account"
      :class="{ 'is-open': accountOpen }"
      type="button"
      aria-label="打开账号菜单"
      aria-haspopup="menu"
      :aria-expanded="accountOpen"
      aria-controls="account-panel"
      @click="accountOpen = !accountOpen"
    >
      <span class="account__avatar">
        <img src="@/assets/brand.svg" alt="" width="26" height="26" />
      </span>
      <span class="account__label">账号</span>
      <ChevronDown
        class="account__chevron"
        :class="{ 'is-open': accountOpen }"
        :size="14"
        aria-hidden="true"
      />
    </button>

    <Transition name="account-menu">
      <section
        v-if="accountOpen"
        id="account-panel"
        class="account-card"
        role="menu"
        aria-label="账号菜单"
      >
        <div class="account-card__avatar">
          <img src="@/assets/brand.svg" alt="" width="82" height="82" />
        </div>

        <div class="account-card__identity">
          <h2>crawler_user</h2>
        </div>

        <nav class="account-links" aria-label="账号功能">
          <RouterLink role="menuitem" to="/user" @click="closeAccountMenu()">
            <UserRound :size="19" aria-hidden="true" />
            <span>个人中心</span>
            <ChevronRight :size="17" aria-hidden="true" />
          </RouterLink>
        </nav>

        <div class="account-card__empty" aria-hidden="true"></div>

        <div class="account-link-divider"></div>

        <button class="account-signout" type="button" role="menuitem" @click="handleSignOut">
          <LogOut :size="19" aria-hidden="true" />
          <span>退出登录</span>
        </button>
      </section>
    </Transition>
  </div>
</template>

<style scoped>
.account-menu {
  position: relative;
}

.account {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 13px;
  color: var(--text-muted);
  text-decoration: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 999px;
  cursor: pointer;
  transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease;
}

.account:hover,
.account.is-open {
  color: var(--text);
  background: var(--bg);
  border-color: var(--border-strong);
}

.account__avatar {
  display: grid;
  flex: none;
  width: 26px;
  height: 26px;
  overflow: hidden;
  background: var(--accent-soft);
  border-radius: 50%;
  place-items: center;
}

.account__avatar img {
  display: block;
  width: 100%;
  height: 100%;
}

.account__label {
  line-height: 1;
}

.account__chevron {
  transition: transform 0.18s ease;
}

.account__chevron.is-open {
  transform: rotate(180deg);
}

.account-card {
  position: absolute;
  top: calc(100% + 14px);
  right: 0;
  z-index: 40;
  width: min(360px, calc(100vw - 24px));
  padding: 0 20px 12px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 18px 48px rgba(22, 25, 31, 0.16), 0 2px 8px rgba(22, 25, 31, 0.08);
}

.account-card__avatar {
  display: grid;
  width: 82px;
  height: 82px;
  margin: -41px auto 9px;
  overflow: hidden;
  background: var(--accent-soft);
  border: 4px solid var(--surface);
  border-radius: 50%;
  box-shadow: 0 3px 12px rgba(22, 25, 31, 0.12);
  place-items: center;
}

.account-card__avatar img {
  display: block;
  width: 100%;
  height: 100%;
}

.account-card__identity {
  text-align: center;
}

.account-card__identity h2 {
  margin: 0;
  color: var(--text);
  font-size: 20px;
  font-weight: 600;
  line-height: 1.4;
}

.account-card__identity p {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin: 5px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.account-card__identity strong {
  color: var(--text);
  font-weight: 500;
}

.account-level {
  margin-top: 18px;
}

.account-level__progress {
  display: flex;
  align-items: center;
  gap: 9px;
}

.account-level__badge,
.account-level__next {
  flex: none;
  color: #d88a16;
  font-size: 11px;
  font-style: italic;
  font-weight: 800;
}

.account-level__next {
  color: var(--text-faint);
}

.account-level__track {
  flex: 1;
  height: 5px;
  overflow: hidden;
  background: #f7ecd8;
  border-radius: 999px;
}

.account-level__track span {
  display: block;
  width: 68%;
  height: 100%;
  background: #f3b44e;
  border-radius: inherit;
}

.account-level > p {
  margin: 8px 0 0;
  color: var(--text-faint);
  font-size: 11px;
  text-align: center;
}

.account-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin: 18px 0 16px;
}

.account-stats div {
  display: flex;
  flex-direction: column-reverse;
  align-items: center;
  gap: 2px;
}

.account-stats dd {
  margin: 0;
  color: var(--text);
  font-size: 22px;
  line-height: 1.2;
}

.account-stats dt {
  color: var(--text-muted);
  font-size: 12px;
}

.account-membership {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: #fff0f5;
  border: 1px solid #f8dce7;
  border-radius: 6px;
}

.account-membership div {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.account-membership strong {
  color: var(--accent-strong);
  font-size: 13px;
  font-weight: 500;
}

.account-membership span {
  color: var(--accent-strong);
  font-size: 12px;
}

.account-membership a {
  flex: none;
  padding: 5px 10px;
  color: var(--accent-strong);
  font-size: 12px;
  text-decoration: none;
  background: var(--surface);
  border: 1px solid #f4cfe0;
  border-radius: 4px;
}

.account-links {
  display: flex;
  flex-direction: column;
  margin-top: 10px;
}

.account-card__empty {
  min-height: 320px;
}

.account-links a,
.account-theme,
.account-signout {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 44px;
  padding: 0 8px;
  color: var(--text-muted);
  font-size: 13px;
  text-align: left;
  text-decoration: none;
  background: transparent;
  border: 0;
  border-radius: 4px;
  cursor: pointer;
}

.account-links a:hover,
.account-theme:hover,
.account-signout:hover {
  color: var(--text);
  background: var(--bg);
}

.account-links a svg,
.account-theme svg,
.account-signout svg {
  justify-self: center;
}

.account-links a svg:last-child,
.account-theme svg:last-child {
  color: var(--text-faint);
}

.account-link-divider {
  height: 1px;
  margin: 5px 8px;
  background: var(--border);
}

.account-theme {
  grid-template-columns: 24px minmax(0, 1fr) 18px;
}

.account-signout {
  grid-template-columns: 24px minmax(0, 1fr);
}

.account-menu-enter-active,
.account-menu-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.account-menu-enter-from,
.account-menu-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}

@media (max-width: 480px) {
  .account {
    width: 36px;
    padding: 0;
    justify-content: center;
  }

  .account__label,
  .account__chevron {
    display: none;
  }

  .account-card {
    position: fixed;
    top: 66px;
    right: 12px;
    left: 12px;
    width: auto;
    max-height: calc(100vh - 78px);
    padding-top: 14px;
    overflow-y: auto;
  }

  .account-card__avatar {
    width: 72px;
    height: 72px;
    margin: 0 auto 9px;
  }

  .account-card__empty {
    min-height: 220px;
  }
}
</style>
