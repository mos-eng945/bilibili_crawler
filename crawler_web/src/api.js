// 开发环境默认使用同源 /api，由 Vite 代理转发到后端。
const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function getErrorMessage(data) {
  if (!data || typeof data !== 'object') {
    return '请求失败'
  }

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

/**
 * 读取API响应数据
 * @param {*} response 
 * @returns 
 */
async function readResponseData(response) {
  try {
    return await response.json()
  } catch {
    // 空响应或非 JSON 响应交给 getErrorMessage 统一处理
    return {}
  }
}


/**
 * 解析API响应
 * @param {*} response 
 * @returns 请求体,或报错message
 */
async function parseResponse(response) {
  const data = await readResponseData(response)

  if (!response.ok) {
    throw new Error(getErrorMessage(data))
  }

  return data
}


/**

Download
{
  "message": "注册成功,
  "token": "",
  "user": {
    "username": "",
    "avatar": "https://example.com/default-avatar.png"
  }
}} payload 
 */
export async function registerAccount(payload) {
  const response = await fetch(`${BASE_URL}/api/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return parseResponse(response)
}


/**
Response body
Download
{
  "message": "登录成功",
  "token": ",
  "user": {
    "username": "admin1234",
    "avatar": "https://example.com/default-avatar.png"
  }
}
 */
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

