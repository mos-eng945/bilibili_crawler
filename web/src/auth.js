import { ref } from 'vue'

const AUTH_KEY = 'crawler-web-authenticated'

export const ACCOUNT_MAX_LENGTH = 32
export const PASSWORD_MIN_LENGTH = 6
export const PASSWORD_MAX_LENGTH = 32

/** 读取认证状态返回T/F */
function readAuthState()
{
  if (localStorage.getItem(AUTH_KEY) === '1') return true
  if (sessionStorage.getItem(AUTH_KEY) === '1') return true
  return false
}

export const authenticated = ref(readAuthState())

/** 记住我,选了就存local为1,没选中就存session为1 */
export function signIn(remember)
{
  authenticated.value = true

  if (remember) {
    localStorage.setItem(AUTH_KEY, '1')
    sessionStorage.removeItem(AUTH_KEY)
    return
  }

  sessionStorage.setItem(AUTH_KEY, '1')
  localStorage.removeItem(AUTH_KEY)
}

/** 登出 */
export function signOut() {
  authenticated.value = false
  localStorage.removeItem(AUTH_KEY)
  sessionStorage.removeItem(AUTH_KEY)
}
