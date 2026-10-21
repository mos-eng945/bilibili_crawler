<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import { signIn } from '@/auth'

const loading = ref(false)
const error = ref('')
const route = useRoute()
const router = useRouter()

function handleLogin({ username, password, remember }) {
  loading.value = true
  error.value = ''

  // 当前仅实现前端登录流程，接入接口后在这里替换成本地校验。
  if (!username || !password) {
    error.value = '请输入账号和密码'
    loading.value = false
    return
  }

  signIn(remember)
  loading.value = false

  const redirect = route.query.redirect
  if (typeof redirect === 'string' && redirect.startsWith('/') && !redirect.startsWith('//')) {
    router.replace(redirect)
    return
  }

  router.replace('/overview')
}
</script>

<template>
  <LoginView :loading="loading" :error="error" @submit="handleLogin" />
</template>
