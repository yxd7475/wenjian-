import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
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
    fetchCurrentUser
  }
})
