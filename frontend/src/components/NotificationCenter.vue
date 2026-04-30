<template>
  <div class="notification-center">
    <el-popover
      ref="popoverRef"
      placement="bottom"
      :width="420"
      trigger="click"
      @show="loadNotifications"
    >
      <template #reference>
        <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
          <el-button :icon="Bell" circle />
        </el-badge>
      </template>

      <div class="notification-list">
        <div class="notification-header">
          <span>通知消息</span>
          <div class="header-actions">
            <el-button text type="primary" size="small" @click="markAllRead">
              全部已读
            </el-button>
          </div>
        </div>

        <el-scrollbar max-height="400px">
          <div v-if="notifications.length === 0" class="empty-notification">
            暂无通知
          </div>
          <div
            v-for="notification in notifications"
            :key="notification.id"
            class="notification-item"
            :class="{ unread: !notification.is_read, clickable: isClickable(notification) }"
            @click="handleNotificationClick(notification)"
          >
            <div class="notification-icon">
              <el-icon :size="20" :color="getIconColor(notification.notification_type)">
                <component :is="getIcon(notification.notification_type)" />
              </el-icon>
            </div>
            <div class="notification-content">
              <div class="notification-title">{{ notification.title }}</div>
              <div class="notification-desc">{{ notification.content }}</div>
              <div class="notification-time">{{ formatTime(notification.created_at) }}</div>

              <!-- 群组邀请操作按钮 -->
              <div v-if="notification.notification_type === 'group_invite' && !notification.is_read && (notification.related_id || notification.data?.invitation_id)" class="notification-actions">
                <el-button type="primary" size="small" @click.stop="acceptInvite(notification)">
                  接受
                </el-button>
                <el-button size="small" @click.stop="rejectInvite(notification)">
                  拒绝
                </el-button>
              </div>
            </div>
          </div>
        </el-scrollbar>
      </div>
    </el-popover>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, Message, User, Document, Folder, ChatDotRound, Warning, CircleCheck } from '@element-plus/icons-vue'
import { notificationService } from '@/utils/notifications'
import api from '@/utils/api'

const router = useRouter()
const popoverRef = ref(null)

const notifications = ref([])
const unreadCount = computed(() => {
  return notifications.value.filter(n => !n.is_read).length
})

// 从后端加载通知
const loadNotifications = async () => {
  try {
    const data = await api.get('/notifications?limit=50')
    // 按时间倒序排列，新消息在前；未读消息优先
    notifications.value = data.sort((a, b) => {
      // 未读优先
      if (a.is_read !== b.is_read) {
        return a.is_read ? 1 : -1
      }
      // 同状态按时间倒序
      return new Date(b.created_at) - new Date(a.created_at)
    })
  } catch (error) {
    console.error('加载通知失败:', error)
  }
}

// 加载未读数量
const loadUnreadCount = async () => {
  try {
    const data = await api.get('/notifications/unread-count')
    // 更新本地未读状态
    await loadNotifications()
  } catch (error) {
    console.error('加载未读数量失败:', error)
  }
}

const getIcon = (type) => {
  const iconMap = {
    'group_invite': Message,
    'group_invite_accepted': CircleCheck,
    'group_invite_rejected': User,
    'group_joined': User,
    'group_removed': User,
    'group_chat_message': ChatDotRound,
    'friend_request': User,
    'friend_accepted': User,
    'chat_message': ChatDotRound,
    'file_share': Document,
    'system': Bell,
    'alert': Warning
  }
  return iconMap[type] || Bell
}

const getIconColor = (type) => {
  const colorMap = {
    'group_invite': '#409EFF',
    'group_invite_accepted': '#67C23A',
    'group_invite_rejected': '#F56C6C',
    'group_joined': '#67C23A',
    'group_removed': '#F56C6C',
    'group_chat_message': '#409EFF',
    'friend_request': '#E6A23C',
    'friend_accepted': '#67C23A',
    'chat_message': '#409EFF',
    'file_share': '#409EFF',
    'system': '#909399',
    'alert': '#F56C6C'
  }
  return colorMap[type] || '#909399'
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  const now = new Date()
  const diff = now - date

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN')
}

// 判断通知是否可点击跳转
const isClickable = (notification) => {
  const clickableTypes = [
    'group_invite', 'group_invite_accepted', 'group_invite_rejected', 'group_joined', 'group_removed',
    'chat_message', 'group_chat_message', 'friend_request', 'friend_accepted', 'file_share'
  ]
  return clickableTypes.includes(notification.notification_type)
}

// 处理通知点击跳转
const handleNotificationClick = async (notification) => {
  if (!isClickable(notification)) return

  // 标记为已读
  if (!notification.is_read) {
    try {
      await api.put(`/notifications/${notification.id}/read`)
      notification.is_read = true
    } catch (error) {
      console.error('标记已读失败:', error)
    }
  }

  // 关闭弹出框
  if (popoverRef.value) {
    popoverRef.value.hide()
  }

  // 根据通知类型跳转
  const type = notification.notification_type
  const data = notification.data || {}

  switch (type) {
    case 'group_invite':
      // 群组邀请跳转到邀请列表页
      router.push('/invitations')
      break
    case 'group_invite_accepted':
    case 'group_invite_rejected':
    case 'group_joined':
      // 跳转到群组详情或群组列表
      if (data.group_id || notification.related_id) {
        router.push(`/groups/${data.group_id || notification.related_id}`)
      } else {
        router.push('/groups')
      }
      break
    case 'group_removed':
      // 被移出群组，跳转到群组列表
      router.push('/groups')
      break
    case 'chat_message':
      if (data.sender_id || notification.related_id) {
        router.push(`/chat?friendId=${data.sender_id || notification.related_id}`)
      } else {
        router.push('/chat')
      }
      break
    case 'group_chat_message':
      if (data.group_id || notification.related_id) {
        router.push(`/chat?groupId=${data.group_id || notification.related_id}`)
      } else {
        router.push('/chat')
      }
      break
    case 'friend_request':
    case 'friend_accepted':
      // 跳转到好友页面
      router.push('/friends')
      break
    case 'file_share':
      // 跳转到文件页面
      router.push('/files')
      break
  }
}

// 接受群组邀请
const acceptInvite = async (notification) => {
  try {
    // 从notification.data或related_id获取invitation_id
    const invitationId = notification.related_id || notification.data?.invitation_id
    if (!invitationId) {
      ElMessage.error('邀请信息无效')
      return
    }
    await api.post(`/groups/invitation/${invitationId}/accept`)
    ElMessage.success('已加入群组')
    notification.is_read = true
    // 重新加载通知
    await loadNotifications()
    // 触发群组列表刷新
    window.dispatchEvent(new CustomEvent('group-updated'))
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

// 拒绝群组邀请
const rejectInvite = async (notification) => {
  try {
    const invitationId = notification.related_id || notification.data?.invitation_id
    if (!invitationId) {
      ElMessage.error('邀请信息无效')
      return
    }
    await api.post(`/groups/invitation/${invitationId}/reject`)
    ElMessage.info('已拒绝邀请')
    notification.is_read = true
    await loadNotifications()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

// 标记全部已读
const markAllRead = async () => {
  try {
    await api.put('/notifications/read-all')
    notifications.value.forEach(n => n.is_read = true)
    ElMessage.success('已全部标记为已读')
  } catch (error) {
    console.error('标记已读失败:', error)
  }
}

// 处理 WebSocket 消息
const handleWebSocketMessage = async (message) => {
  const { type, data } = message

  // 忽略心跳响应和其他非通知消息
  const notificationTypes = [
    'group_invite', 'group_invite_accepted', 'group_invite_rejected', 'group_joined', 'group_removed',
    'chat_message', 'group_chat_message', 'friend_request', 'friend_accepted', 'notification', 'alert'
  ]
  if (!notificationTypes.includes(type)) {
    return
  }

  // 重新加载通知
  await loadNotifications()

  // 显示消息提示
  let title = ''
  switch (type) {
    case 'group_invite':
      title = `${data.inviter_name} 邀请您加入群组「${data.group_name}」`
      break
    case 'group_invite_accepted':
      title = `${data.user_name} 已接受您的群组邀请`
      break
    case 'group_invite_rejected':
      title = `${data.user_name} 拒绝了您的群组邀请`
      break
    case 'group_joined':
      title = `您已加入群组「${data.group_name}」`
      break
    case 'group_removed':
      title = `您已被移出群组「${data.group_name}」`
      break
    case 'chat_message':
    case 'group_chat_message':
      title = `群组「${data.group_name}」有新消息`
      break
    case 'friend_request':
      title = '新的好友申请'
      break
    case 'friend_accepted':
      title = '好友申请已通过'
      break
    default:
      return // 不显示提示
  }

  if (title) {
    ElMessage({
      type: type === 'group_removed' ? 'warning' : 'info',
      message: title,
      duration: 3000
    })
  }
}

onMounted(() => {
  loadNotifications()
  // 注册 WebSocket 消息监听
  notificationService.on('*', handleWebSocketMessage)
})

onUnmounted(() => {
  notificationService.off('*', handleWebSocketMessage)
})

// 暴露方法供外部使用
defineExpose({
  loadNotifications,
  loadUnreadCount
})
</script>

<style scoped>
.notification-center {
  display: inline-block;
}

.notification-list {
  max-height: 450px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
  margin-bottom: 10px;
  font-weight: bold;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notification-item {
  display: flex;
  padding: 12px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.notification-item.clickable {
  cursor: pointer;
}

.notification-item:hover {
  background-color: #f5f7fa;
}

.notification-item.unread {
  background-color: #ecf5ff;
}

.notification-item.unread.clickable:hover {
  background-color: #d9ecff;
}

.notification-icon {
  margin-right: 12px;
  display: flex;
  align-items: center;
}

.notification-content {
  flex: 1;
}

.notification-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.notification-desc {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.notification-time {
  font-size: 11px;
  color: #c0c4cc;
}

.notification-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.empty-notification {
  text-align: center;
  padding: 40px 0;
  color: #909399;
}
</style>
