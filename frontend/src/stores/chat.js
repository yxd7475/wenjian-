import { ref, computed } from 'vue'
import api from '@/utils/api'

// 全局消息状态
const unreadCount = ref(0)

export const useChatStore = () => {
  // 获取未读消息数
  const fetchUnreadCount = async () => {
    try {
      const result = await api.get('/chat/unread-count')
      unreadCount.value = result.unread_count
    } catch (error) {
      console.error('获取未读消息数失败:', error)
    }
  }

  // 增加未读数
  const increaseUnread = (count = 1) => {
    unreadCount.value += count
  }

  // 减少未读数
  const decreaseUnread = (count = 1) => {
    unreadCount.value = Math.max(0, unreadCount.value - count)
  }

  // 清零未读数
  const clearUnread = () => {
    unreadCount.value = 0
  }

  // 设置未读数
  const setUnreadCount = (count) => {
    unreadCount.value = count
  }

  return {
    unreadCount: computed(() => unreadCount.value),
    fetchUnreadCount,
    increaseUnread,
    decreaseUnread,
    clearUnread,
    setUnreadCount
  }
}
