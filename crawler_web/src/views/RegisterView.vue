<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Lock, User, UserPlus } from '@lucide/vue'

import {
  ACCOUNT_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  setSession,
} from '@/auth'
import { registerAccount } from '@/api'

const router = useRouter()
const account = ref('')
const password = ref('')
const confirmation = ref('')
const blurred = ref({ account: false, password: false, confirmation: false })
const submitted = ref(false)
const loading = ref(false)
const apiError = ref('')

const errors = computed(() => {
  const result = {
    account: '',
    password: '',
    confirmation: '',
  }

  const trimmedAccount = account.value.trim()

  if (!trimmedAccount) {
    result.account = '请输入邮箱或用户名'
  } else if (trimmedAccount.length > ACCOUNT_MAX_LENGTH) {
    result.account = `账号不能超过 ${ACCOUNT_MAX_LENGTH} 个字符`
  }

  if (password.value.length < PASSWORD_MIN_LENGTH) {
    result.password = `密码至少需要 ${PASSWORD_MIN_LENGTH} 位`
  } else if (password.value.length > PASSWORD_MAX_LENGTH) {
    result.password = `密码不能超过 ${PASSWORD_MAX_LENGTH} 个字符`
  }

  if (!confirmation.value) {
    result.confirmation = '请再次输入密码'
  } else if (confirmation.value.length > PASSWORD_MAX_LENGTH) {
    result.confirmation = `密码不能超过 ${PASSWORD_MAX_LENGTH} 个字符`
  } else if (confirmation.value !== password.value) {
    result.confirmation = '两次输入的密码不一致'
  }

  return result
})

const isValid = computed(() => {
  if (errors.value.account) return false
  if (errors.value.password) return false
  if (errors.value.confirmation) return false
  return true
})

function errorFor(field) {
  if (!blurred.value[field] && !submitted.value) return ''
  return errors.value[field]
}

async function handleSubmit() {
  submitted.value = true

  if (!isValid.value) return

  loading.value = true
  apiError.value = ''

  try {
    const data = await registerAccount({
      username: account.value.trim(),
      password: password.value,
      confirm_password: confirmation.value,
    })
    setSession(data.token, true)
    router.replace('/overview')
  } catch (err) {
    apiError.value = err.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register">
    <main class="panel">
      <img class="panel__mark" src="@/assets/brand.svg" alt="" width="48" height="48" />
      <h1 class="panel__title">创建账号</h1>
      <p class="panel__description">注册后进入 Bilibili 数据分析台。</p>

      <form class="form" novalidate @submit.prevent="handleSubmit">
        <div class="field">
          <label class="field__label" for="register-account">账号</label>
          <div class="field__box" :class="{ 'is-invalid': errorFor('account') }">
            <User class="field__icon" :size="16" aria-hidden="true" />
            <input
              id="register-account"
              v-model="account"
              name="account"
              type="text"
              autocomplete="username"
              placeholder="邮箱或用户名"
              :aria-invalid="Boolean(errorFor('account'))"
              @blur="blurred.account = true"
            />
          </div>
          <p v-if="errorFor('account')" class="field__error">{{ errorFor('account') }}</p>
        </div>

        <div class="field">
          <label class="field__label" for="register-password">密码</label>
          <div class="field__box" :class="{ 'is-invalid': errorFor('password') }">
            <Lock class="field__icon" :size="16" aria-hidden="true" />
            <input
              id="register-password"
              v-model="password"
              name="password"
              type="password"
              autocomplete="new-password"
              placeholder="至少 8 位"
              :aria-invalid="Boolean(errorFor('password'))"
              @blur="blurred.password = true"
            />
          </div>
          <p v-if="errorFor('password')" class="field__error">{{ errorFor('password') }}</p>
        </div>

        <div class="field">
          <label class="field__label" for="register-confirmation">确认密码</label>
          <div class="field__box" :class="{ 'is-invalid': errorFor('confirmation') }">
            <Lock class="field__icon" :size="16" aria-hidden="true" />
            <input
              id="register-confirmation"
              v-model="confirmation"
              name="confirmation"
              type="password"
              autocomplete="new-password"
              placeholder="再次输入密码"
              :aria-invalid="Boolean(errorFor('confirmation'))"
              @blur="blurred.confirmation = true"
            />
          </div>
          <p v-if="errorFor('confirmation')" class="field__error">
            {{ errorFor('confirmation') }}
          </p>
        </div>

        <p v-if="apiError" class="field__error">{{ apiError }}</p>

        <button class="submit" type="submit" :disabled="loading">
          <UserPlus :size="16" aria-hidden="true" />
          <span>{{ loading ? '注册中' : '注册并进入' }}</span>
        </button>
      </form>

      <p class="auth-switch">
        已有账号？
        <RouterLink to="/login">返回登录</RouterLink>
      </p>
    </main>
  </div>
</template>

<style scoped>
.register {
  display: grid;
  place-items: center;
  min-height: 100%;
  padding: 40px 20px;
}

.panel {
  width: 100%;
  max-width: 400px;
  padding: 32px 28px 26px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-panel);
}

.panel__mark {
  display: block;
}

.panel__title {
  margin: 14px 0 0;
  color: var(--text-strong);
  font-size: 18px;
  font-weight: 700;
}

.panel__description {
  margin: 7px 0 24px;
  color: var(--text-muted);
  font-size: 12px;
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

.field__error {
  margin: 0;
  color: var(--danger);
  font-size: 12px;
}

.submit {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 42px;
  margin-top: 2px;
  color: #ffffff;
  background: var(--accent);
  border: 1px solid transparent;
  border-radius: var(--radius);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.submit:hover {
  background: var(--accent-strong);
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

@media (max-width: 420px) {
  .register {
    padding: 24px 16px;
  }

  .panel {
    padding: 26px 20px 24px;
  }
}
</style>
