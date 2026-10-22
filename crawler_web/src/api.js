const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function getErrorMessage(data) {
  if (typeof data.detail === 'string') {
    return data.detail
  }

  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => item.msg || '请求参数错误')
      .join('；')
  }

  return '请求失败'
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(getErrorMessage(data))
  }
  return data
}

export async function registerAccount(payload) {
  const response = await fetch(`${BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse(response)
}

export async function loginAccount(payload) {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse(response)
}

export async function getProfile(token) {
  const response = await fetch(`${BASE_URL}/api/user/profile`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return parseResponse(response)
}

