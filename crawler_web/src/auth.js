import { ref } from 'vue'

const TOKEN_KEY = 'crawler-web-token'

export const ACCOUNT_MAX_LENGTH = 20
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 64

/**
 * 获得token
 */
function readToken() {
  const localToken = localStorage.getItem(TOKEN_KEY)
  if (localToken) {
    return localToken
  }

  const sessionToken = sessionStorage.getItem(TOKEN_KEY)
  if (sessionToken) {
    return sessionToken
  }

  return ''
}

export const token = ref(readToken())
export const authenticated = ref(Boolean(token.value))

/** 
 * 设置会话,remember为true时,token存储在localStorage,否则存储在sessionStorage
 */
export function setSession(tokenValue, remember) {
  token.value = tokenValue
  authenticated.value = true

  if (remember) {
    localStorage.setItem(TOKEN_KEY, tokenValue)
    sessionStorage.removeItem(TOKEN_KEY)
    return
  }

  sessionStorage.setItem(TOKEN_KEY, tokenValue)
  localStorage.removeItem(TOKEN_KEY)
}




/**登出将auth状态重置,并清除存储的token */
export function signOut() {
  token.value = ''
  authenticated.value = false
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
}

