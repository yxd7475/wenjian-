import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

// 检查token是否过期
function isTokenExpired(token) {
  if (!token) return true
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (!payload.exp) return false
    // exp是秒级时间戳，比较当前时间
    return Date.now() >= payload.exp * 1000
  } catch {
    return true
  }
}

// 初始化时检查token有效性
function getValidToken() {
  const token = localStorage.getItem('token') || ''
  if (token && isTokenExpired(token)) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    return ''
  }
  return token
}

function getValidUser() {
  const token = localStorage.getItem('token') || ''
  if (token && isTokenExpired(token)) {
    return null
  }
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

export const useUserStore = defineStore('user', () => {
  const token = ref(getValidToken())
  const user = ref(getValidUser())

  const isLoggedIn = computed(() => !!token.value && !isTokenExpired(token.value))
  const isAdmin = computed(() => {
    if (!user.value) return false
    if (user.value.is_superuser) return true
    if (user.value.role && (user.value.role.code === 'admin' || user.value.role.code === 'super_admin')) return true
    return false
  })

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.access_token
    user.value = res.user
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    return res
  }

  function setToken(newToken) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  function setUser(newUser) {
    user.value = newUser
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function fetchCurrentUser() {
    try {
      const res = await api.get('/auth/me')
      user.value = res
      localStorage.setItem('user', JSON.stringify(res))
      return res
    } catch (error) {
      logout()
      throw error
    }
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    login,
    logout,
    fetchCurrentUser,
    setToken,
    setUser
  }
})
