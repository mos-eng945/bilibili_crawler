<script setup>
import { computed, ref } from 'vue'
import { CircleAlert, Eye, EyeOff, LoaderCircle, LogIn, Lock, User } from '@lucide/vue'

import { ACCOUNT_MAX_LENGTH, PASSWORD_MAX_LENGTH } from '@/auth'

// 页面只负责"收集 + 校验 + 抛出去"，
// 发请求和判断登录成功都属于父组件（以后是接口）的事。
const props = defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['submit'])

const username = ref('')
const password = ref('')
const remember = ref(true)
const revealPassword = ref(false)
const blurred = ref({ username: false, password: false })//模糊
const submitted = ref(false)

const errors = computed(() => {
  const result = {
    username: '',
    password: '',
  }

  const trimmedUsername = username.value.trim()

  if (!trimmedUsername) {
    result.username = '请输入账号'
  } else if (trimmedUsername.length > ACCOUNT_MAX_LENGTH) {
    result.username = `账号不能超过 ${ACCOUNT_MAX_LENGTH} 个字符`
  }

  if (!password.value) {
    result.password = '请输入密码'
  } else if (password.value.length > PASSWORD_MAX_LENGTH) {
    result.password = `密码不能超过 ${PASSWORD_MAX_LENGTH} 个字符`
  }

  return result
})

const isValid = computed(() => !errors.value.username && !errors.value.password) // 登录有效?
const passwordInputType = computed(() => {
  if (revealPassword.value) return 'text'
  return 'password'
})
const passwordToggleText = computed(() => {
  if (revealPassword.value) return '隐藏密码'
  return '显示密码'
})
const passwordToggleIcon = computed(() => {
  if (revealPassword.value) return EyeOff
  return Eye
})
const submitText = computed(() => {
  if (props.loading) return '登录中'
  return '登录'
})

// 字段先被离开或提交过一次才报错，避免用户刚点进来就看到一片红
function errorFor(field) {
  if (!blurred.value[field] && !submitted.value) return ''
  return errors.value[field]
}

function handleSubmit() {
  submitted.value = true

  if (!isValid.value || props.loading) return

  emit('submit', {
    username: username.value.trim(),
    password: password.value,
    remember: remember.value,
  })
}
</script>

<template>
  <div class="login">
    <main class="panel">
      <img class="panel__mark" src="@/assets/brand.svg" alt="" width="48" height="48" />
      <h1 class="panel__title">Bilibili 数据分析台</h1>

      <form class="form" novalidate @submit.prevent="handleSubmit">
        <div class="field">
          <label class="field__label" for="username">账号</label>
          <div class="field__box" :class="{ 'is-invalid': errorFor('username') }">
            <User class="field__icon" :size="16" aria-hidden="true" />
            <input
              id="username"
              v-model="username"
              name="username"
              type="text"
              autocomplete="username"
              placeholder="手机号 / 邮箱"
              :disabled="loading"
              :aria-invalid="Boolean(errorFor('username'))"
              @blur="blurred.username = true"
            />
          </div>
          <p v-if="errorFor('username')" class="field__error">{{ errorFor('username') }}</p>
        </div>

        <div class="field">
          <label class="field__label" for="password">密码</label>
          <div class="field__box" :class="{ 'is-invalid': errorFor('password') }">
            <Lock class="field__icon" :size="16" aria-hidden="true" />
            <input
              id="password"
              v-model="password"
              name="password"
              :type="passwordInputType"
              autocomplete="current-password"
              placeholder="请输入密码"
              :disabled="loading"
              :aria-invalid="Boolean(errorFor('password'))"
              @blur="blurred.password = true"
            />
            <button
              class="field__toggle"
              type="button"
              :aria-label="passwordToggleText"
              :title="passwordToggleText"
              :disabled="loading"
              @click="revealPassword = !revealPassword"
            >
              <component :is="passwordToggleIcon" :size="16" aria-hidden="true" />
            </button>
          </div>
          <p v-if="errorFor('password')" class="field__error">{{ errorFor('password') }}</p>
        </div>

        <label class="check">
          <input v-model="remember" type="checkbox" :disabled="loading" />
          <span>记住我</span>
        </label>

        <p v-if="error" class="alert" role="alert">
          <CircleAlert :size="16" aria-hidden="true" />
          <span>{{ error }}</span>
        </p>

        <button class="submit" type="submit" :disabled="loading">
          <LoaderCircle v-if="loading" class="spin" :size="16" aria-hidden="true" />
          <LogIn v-else :size="16" aria-hidden="true" />
          <span>{{ submitText }}</span>
        </button>
      </form>

      <p class="auth-switch">
        还没有账号？
        <RouterLink to="/register">注册账号</RouterLink>
      </p>
    </main>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  place-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.panel {
  width: 100%;
  max-width: 380px;
  padding: 32px 28px 28px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-panel);
}

.panel__mark {
  display: block;
}

.panel__title {
  margin: 14px 0 26px;
  color: var(--text-strong);
  font-size: 18px;
  font-weight: 700;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.field__box {
  position: relative;
  display: flex;
  align-items: center;
  height: 40px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.field__box:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.field__box.is-invalid {
  border-color: var(--danger);
}

.field__box.is-invalid:focus-within {
  box-shadow: 0 0 0 3px var(--danger-soft);
}

.field__icon {
  flex: none;
  margin-left: 12px;
  color: var(--text-faint);
}

.field__box input {
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 10px;
  background: transparent;
  border: 0;
  outline: none;
}

.field__box input::placeholder {
  color: var(--text-faint);
}

.field__box:has(.field__toggle) input {
  padding-right: 0;
}

.field__toggle {
  display: grid;
  place-items: center;
  flex: none;
  width: 34px;
  height: 100%;
  margin-right: 3px;
  color: var(--text-faint);
  background: transparent;
  border: 0;
  border-radius: var(--radius);
  cursor: pointer;
}

.field__toggle:hover:not(:disabled) {
  color: var(--text-muted);
}

.field__error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.check {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  user-select: none;
}

.check input {
  width: 15px;
  height: 15px;
  margin: 0;
  accent-color: var(--accent);
  cursor: pointer;
}

.alert {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 10px 12px;
  color: var(--danger);
  background: var(--danger-soft);
  border-radius: var(--radius);
  font-size: 13px;
}

.alert svg {
  flex: none;
}

.submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  color: #ffffff;
  background: var(--accent);
  border: 1px solid transparent;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.submit:hover:not(:disabled) {
  background: var(--accent-strong);
}

.submit:disabled {
  cursor: default;
  opacity: 0.7;
}

.auth-switch {
  margin: 18px 0 0;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}

.auth-switch a {
  color: var(--accent-strong);
  font-weight: 600;
  text-decoration: none;
}

.auth-switch a:hover {
  text-decoration: underline;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin {
    animation: none;
  }
}

@media (max-width: 420px) {
  .login {
    padding: 24px 16px;
  }

  .panel {
    padding: 26px 20px 24px;
  }
}
</style>
