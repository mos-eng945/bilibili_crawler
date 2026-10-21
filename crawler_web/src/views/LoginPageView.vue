<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CircleAlert, Eye, EyeOff, LoaderCircle, LogIn, Lock, User } from '@lucide/vue'

import { ACCOUNT_MAX_LENGTH, PASSWORD_MAX_LENGTH, signIn } from '@/auth'

const loading = ref(false)
const error = ref('')
const username = ref('')
const password = ref('')
const remember = ref(true)
const revealPassword = ref(false)
const blurred = ref({ username: false, password: false })//模糊
const submitted = ref(false)
const route = useRoute()
const router = useRouter()
/**
 * 计算错误信息
 * 1. 用户名和密码都不能为空
 * 2. 用户名和密码长度不能超过最大值32,最小长度为6
 */
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

const isValid = computed(() => !errors.value.username && !errors.value.password) // 登录有效 没有错误的username和password

/**
 * 计算密码输入框的类型
 * 如果需要显示密码，则返回 'text'，否则返回 'password'
 */
const passwordInputType = computed(() => {
  if (revealPassword.value) return 'text'
  return 'password'
})

/**
 * 计算密码切换按钮的文本和图标
 * 如果需要显示密码，则返回 '隐藏密码' 和 EyeOff 图标，否则返回 '显示密码' 和 Eye 图标
 */
const passwordToggleText = computed(() => {
  if (revealPassword.value) return '隐藏密码'
  return '显示密码'
})

/**
 * 计算密码切换按钮的图标
 * 如果需要显示密码，则返回 EyeOff 图标，否则返回 Eye 图标
 */
const passwordToggleIcon = computed(() => {
  if (revealPassword.value) return EyeOff
  return Eye
})
const submitText = computed(() => {
  if (loading.value) return '登录中'
  return '登录'
})

/**
 * 字段先被离开或提交过一次才报错，避免用户刚点进来就看到一片红
 * 返回当前字段的错误信息,如果没有错误则返回空字符串
 */
function errorFor(field) {
  if (!blurred.value[field] && !submitted.value) return ''
  return errors.value[field]
}
/**
 * 处理表单提交
 */
function handleSubmit() {
  submitted.value = true

  if (!isValid.value || loading.value) return

  loading.value = true
  error.value = ''
  signIn(remember.value)
  loading.value = false

  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    router.replace(redirect)
    return
  }

  router.replace('/project')
}
</script>

<template>
  <div class="login">
    <main class="panel">
      <img class="panel__mark" src="@/assets/brand.svg" alt="" width="48" height="48" />
      <h1 class="panel__title">Bilibili 数据分析台</h1>
      <!--novalidate 禁止浏览器默认的表单验证，使用自定义验证-->
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
              <!-- 用户离开输入框时设置为 true, 用于控制错误信息的显示 ,避免一进来就看到一片红-->

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
            <!-- @blur用户离开输入框时设置为 true, 用于控制错误信息的显示 ,避免一进来就看到一片红-->
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

            <!-- 取反切换是否可见 -->
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
