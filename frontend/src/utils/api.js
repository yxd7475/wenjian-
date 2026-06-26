import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const api = axios.create({
  baseURL: '/files/api',
  timeout: 30000
})

// 检查token是否过期
function isTokenExpired(token) {
  if (!token) return true
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (!payload.exp) return false
    return Date.now() >= payload.exp * 1000
  } catch {
    return true
  }
}

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      if (isTokenExpired(token)) {
        // token已过期，清除并跳转登录
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push({ name: 'Login' })
        return Promise.reject(new Error('登录已过期，请重新登录'))
      }
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.detail || '请求失败'

    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push({ name: 'Login' })
      ElMessage.error('登录已过期，请重新登录')
    } else if (status === 403) {
      ElMessage.error('没有权限执行此操作')
    } else if (status === 404) {
      ElMessage.error('资源不存在')
    } else {
      ElMessage.error(message)
    }

    return Promise.reject(error)
  }
)

export default api

export function getDirectApiUrl(path) {
  return path
}
