import { ref } from 'vue'

const TOKEN_KEY = 'crawler-web-token'

export const ACCOUNT_MAX_LENGTH = 20
export const PASSWORD_MIN_LENGTH = 8
export const PASSWORD_MAX_LENGTH = 64

function readToken() {
  return (
    localStorage.getItem(TOKEN_KEY)
    || sessionStorage.getItem(TOKEN_KEY)
    || ''
  )
}

export const token = ref(readToken())
export const authenticated = ref(Boolean(token.value))

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

export function signOut() {
  token.value = ''
  authenticated.value = false
  localStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_KEY)
}

