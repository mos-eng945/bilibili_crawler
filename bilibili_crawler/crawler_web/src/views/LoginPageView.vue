<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import { setSession } from '@/auth'
import { loginAccount } from '@/api'

const loading = ref(false)
const error = ref('')
const route = useRoute()
const router = useRouter()

async function handleLogin({ username, password, remember }) {
  loading.value = true
  error.value = ''

  try {
    const data = await loginAccount({ username, password })
    setSession(data.token, remember)

    const redirect = route.query.redirect
    if (
      typeof redirect === 'string'
      && redirect.startsWith('/')
      && !redirect.startsWith('//')
    ) {
      router.replace(redirect)
      return
    }

    router.replace('/overview')
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <LoginView :loading="loading" :error="error" @submit="handleLogin" />
</template>
