<template>
  <div class="chat-page">
    <div class="chat-container">
      <!-- 左侧对话列表 -->
      <div :class="['conversation-list', { 'mobile-hidden': showChatArea }]">
        <div class="conversation-header">
          <span>消息</span>
          <el-badge :value="totalUnread" :hidden="totalUnread === 0" class="unread-badge" />
        </div>

        <!-- Tab 切换 -->
        <el-tabs v-model="activeTab" class="chat-tabs">
          <el-tab-pane label="好友" name="friends"></el-tab-pane>
          <el-tab-pane label="群组" name="groups"></el-tab-pane>
        </el-tabs>

        <!-- 好友对话列表 -->
        <div class="conversations" v-show="activeTab === 'friends'">
          <div
            v-for="conv in conversations"
            :key="'friend-' + conv.user_id"
            :class="['conversation-item', { active: currentFriendId === conv.user_id && !currentGroupId }]"
            @click="selectFriend(conv.user_id)"
          >
            <el-avatar :size="40" icon="UserFilled" />
            <div class="conv-info">
              <div class="conv-name">{{ conv.real_name || conv.username }}</div>
              <div class="conv-last-msg" v-if="conv.last_message">{{ conv.last_message }}</div>
            </div>
            <el-badge :value="conv.unread_count" :hidden="conv.unread_count === 0" />
          </div>
          <el-empty v-if="conversations.length === 0" description="暂无好友对话" :image-size="80" />
        </div>

        <!-- 群组对话列表 -->
        <div class="conversations" v-show="activeTab === 'groups'">
          <div
            v-for="conv in groupConversations"
            :key="'group-' + conv.group_id"
            :class="['conversation-item', { active: currentGroupId === conv.group_id }]"
            @click="selectGroup(conv.group_id)"
          >
            <el-avatar :size="40" style="background-color: #67C23A">
              <el-icon><UserFilled /></el-icon>
            </el-avatar>
            <div class="conv-info">
              <div class="conv-name">{{ conv.group_name }}</div>
              <div class="conv-last-msg" v-if="conv.last_message">{{ conv.last_message }}</div>
            </div>
          </div>
          <el-empty v-if="groupConversations.length === 0" description="暂无群组对话" :image-size="80" />
        </div>
      </div>

      <!-- 右侧聊天区域 -->
      <div :class="['chat-area', { 'mobile-visible': showChatArea }]">
        <template v-if="currentFriendId || currentGroupId">
          <!-- 聊天头部 -->
          <div class="chat-header">
            <el-button class="back-btn" @click="goBackToList" circle size="small">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <span class="chat-title">{{ chatTitle }}</span>
            <div class="header-actions" v-if="currentGroupId">
              <el-button type="primary" text size="small" @click="showInviteDialog = true">
                <el-icon><Plus /></el-icon>
                邀请好友
              </el-button>
              <el-button type="primary" text size="small" @click="goToGroupSpace">
                <el-icon><Folder /></el-icon>
                群组文件
              </el-button>
            </div>
          </div>

          <!-- 消息列表 -->
          <div class="message-list" ref="messageListRef">
            <div
              v-for="msg in currentMessages"
              :key="msg.id"
              :class="['message-item', { mine: msg.sender_id === currentUserId }]"
            >
              <!-- 头像 -->
              <el-avatar
                v-if="msg.sender_id !== currentUserId"
                :size="36"
                class="avatar"
              >
                {{ getAvatarText(msg) }}
              </el-avatar>

              <div class="message-content">
                <div class="sender-name" v-if="currentGroupId && msg.sender_id !== currentUserId">
                  {{ msg.sender_real_name || msg.sender_name }}
                </div>

                <!-- 文本消息 -->
                <div v-if="!msg.message_type || msg.message_type === 'text'" class="message-bubble">
                  {{ msg.content }}
                </div>

                <!-- 图片消息 -->
                <div v-else-if="msg.message_type === 'image'" class="message-bubble image-bubble">
                  <el-image
                    :src="getFileUrl(msg.file_id)"
                    fit="cover"
                    :preview-src-list="[getFileUrl(msg.file_id)]"
                    class="chat-image"
                  >
                    <template #error>
                      <div class="image-error">
                        <el-icon><Picture /></el-icon>
                        <span>图片加载失败</span>
                      </div>
                    </template>
                  </el-image>
                </div>

                <!-- 文件消息 -->
                <div v-else-if="msg.message_type === 'file'" class="message-bubble file-bubble" @click="handleFileMessageClick(msg)">
                  <div class="file-icon-wrapper" :style="{ background: getFileIconBg({ ext: getFileExtension(msg.file_name) }) }">
                    <el-icon :size="20" color="#fff"><component :is="getFileIcon({ ext: getFileExtension(msg.file_name) })" /></el-icon>
                  </div>
                  <div class="file-info">
                    <div class="file-name">{{ msg.file_name }}</div>
                    <div class="file-size">{{ formatFileSize(msg.file_size) }}</div>
                  </div>
                  <el-icon class="download-icon"><Download /></el-icon>
                </div>

                <div class="message-time">{{ formatTime(msg.created_at) }}</div>
              </div>

              <!-- 自己的头像放右边 -->
              <el-avatar
                v-if="msg.sender_id === currentUserId"
                :size="36"
                class="avatar avatar-mine"
              >
                {{ getAvatarText(msg) }}
              </el-avatar>
            </div>
            <div v-if="currentMessages.length === 0" class="no-messages">
              暂无消息，发送一条消息开始聊天吧
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-toolbar" v-if="currentFriendId || currentGroupId">
              <el-tooltip content="发送图片">
                <el-button circle size="small" @click="sendImage">
                  <el-icon><Picture /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="发送文件">
                <el-button circle size="small" @click="sendFile">
                  <el-icon><Folder /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
            <el-input
              v-model="inputMessage"
              placeholder="输入消息... (Enter发送)"
              @keyup.enter="sendMessage"
              :disabled="sending"
              clearable
            >
              <template #append>
                <el-button @click="sendMessage" :loading="sending">发送</el-button>
              </template>
            </el-input>
          </div>

          <!-- 隐藏的文件上传 -->
          <input type="file" ref="imageInput" @change="handleImageSelect" accept="image/*" style="display: none" />
          <input type="file" ref="fileInput" @change="handleFileSelect" style="display: none" />
        </template>
        <template v-else>
          <div class="no-chat-selected">
            <el-icon :size="60"><ChatDotRound /></el-icon>
            <p>选择一个好友或群组开始聊天</p>
          </div>
        </template>
      </div>
    </div>

    <!-- 邀请好友对话框 -->
    <el-dialog v-model="showInviteDialog" title="邀请好友加入群组" width="450px">
      <div v-if="inviteLoading" style="text-align: center; padding: 20px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <p>加载中...</p>
      </div>
      <div v-else-if="inviteFriends.length === 0" style="text-align: center; padding: 20px; color: #909399">
        <p>暂无可邀请的好友</p>
        <p style="font-size: 12px">所有好友都已在群组中，或您还没有好友</p>
      </div>
      <div v-else class="invite-friend-list">
        <div
          v-for="friend in inviteFriends"
          :key="friend.id"
          class="invite-friend-item"
        >
          <div class="friend-info">
            <el-avatar :size="36">{{ (friend.real_name || friend.username || '?').charAt(0).toUpperCase() }}</el-avatar>
            <span class="friend-name">{{ friend.real_name || friend.username }}</span>
          </div>
          <el-button
            :type="friend.invited ? 'info' : 'primary'"
            size="small"
            @click="!friend.invited && inviteFriend(friend.id)"
            :loading="invitingFriendId === friend.id"
            :disabled="friend.invited"
          >
            {{ friend.invited ? '已邀请' : '邀请' }}
          </el-button>
        </div>
      </div>
    </el-dialog>

    <FilePreviewDialog
      v-model="showPreviewDialog"
      :file="previewFile"
      :preview-url="previewUrl"
      :text-request="fetchPreviewText"
      @download="downloadPreviewFile"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import { ElMessage } from 'element-plus'
import { ChatDotRound, UserFilled, Picture, Folder, Document, Download, ArrowLeft, Plus, Loading, VideoPlay, Headset, Notebook, Files, Grid, DataBoard, Reading } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { notificationService } from '@/utils/notifications'
import { getFileIcon, getFileIconBg } from '@/utils/file'
import FilePreviewDialog from '@/components/FilePreviewDialog.vue'
import { buildFilePreviewUrl, getFileExtension, isPreviewable } from '@/utils/file'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const chatStore = useChatStore()

const activeTab = ref('friends')
const conversations = ref([])
const groupConversations = ref([])
const messages = ref([])
const groupMessages = ref([])
const currentFriendId = ref(null)
const currentGroupId = ref(null)
const inputMessage = ref('')
const sending = ref(false)
const messageListRef = ref(null)
const imageInput = ref(null)
const fileInput = ref(null)
const showPreviewDialog = ref(false)
const previewFile = ref(null)
const previewUrl = ref('')

// 邀请好友相关
const showInviteDialog = ref(false)
const inviteFriends = ref([])
const inviteLoading = ref(false)
const invitingFriendId = ref(null)

const currentUserId = computed(() => userStore.user?.id)

const chatTitle = computed(() => {
  if (currentGroupId.value) {
    const conv = groupConversations.value.find(c => c.group_id === currentGroupId.value)
    return conv?.group_name || '群组聊天'
  }
  if (currentFriendId.value) {
    const conv = conversations.value.find(c => c.user_id === currentFriendId.value)
    return conv?.real_name || conv?.username || '聊天'
  }
  return '聊天'
})

const totalUnread = computed(() => {
  return conversations.value.reduce((sum, c) => sum + c.unread_count, 0)
})

const showChatArea = computed(() => currentFriendId.value || currentGroupId.value)

const currentMessages = computed(() => {
  if (currentGroupId.value) {
    return groupMessages.value
  }
  return messages.value
})

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()

  if (isToday) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } else {
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

const getAvatarText = (msg) => {
  const name = msg.sender_real_name || msg.sender_name || '?'
  return name.charAt(0).toUpperCase()
}

const getFileUrl = (fileId) => {
  if (!fileId) return ''
  const token = localStorage.getItem('token')
  return `/files/api/files/${fileId}/download?token=${token}`
}

const normalizeMessageFile = (msg) => ({
  id: msg.file_id,
  origin_name: msg.file_name,
  size: msg.file_size,
  ext: getFileExtension(msg.file_name)
})

const canPreviewMessageFile = (msg) => {
  if (!msg?.file_id || !msg?.file_name) return false
  return isPreviewable(normalizeMessageFile(msg))
}

const goToGroupSpace = () => {
  if (currentGroupId.value) {
    // 找到群组空间
    router.push(`/spaces?group=${currentGroupId.value}`)
  }
}

// 加载可邀请的好友列表
const loadInviteFriends = async () => {
  if (!currentGroupId.value) return
  inviteLoading.value = true
  try {
    inviteFriends.value = await api.get(`/groups/${currentGroupId.value}/invite-friends`)
  } catch (error) {
    console.error('加载好友列表失败:', error)
  } finally {
    inviteLoading.value = false
  }
}

// 邀请好友加入群组
const inviteFriend = async (friendId) => {
  if (!currentGroupId.value) return
  invitingFriendId.value = friendId
  try {
    await api.post(`/groups/${currentGroupId.value}/invite/${friendId}`)
    ElMessage.success('邀请已发送，等待对方确认')
    // 标记为已邀请状态
    const friend = inviteFriends.value.find(f => f.id === friendId)
    if (friend) {
      friend.invited = true
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '邀请失败')
  } finally {
    invitingFriendId.value = null
  }
}

const loadConversations = async () => {
  try {
    conversations.value = await api.get('/chat/conversations')
  } catch (error) {
    console.error('加载好友对话列表失败:', error)
  }
}

const loadGroupConversations = async () => {
  try {
    groupConversations.value = await api.get('/group-chat/conversations')
  } catch (error) {
    console.error('加载群组对话列表失败:', error)
  }
}

const loadMessages = async () => {
  if (!currentFriendId.value) return
  try {
    messages.value = await api.get(`/chat/messages/${currentFriendId.value}`)
    scrollToBottom()
    // 加载消息后刷新未读数，更新导航栏红点
    chatStore.fetchUnreadCount()
  } catch (error) {
    console.error('加载消息失败:', error)
  }
}

const loadGroupMessages = async () => {
  if (!currentGroupId.value) return
  try {
    groupMessages.value = await api.get(`/group-chat/messages/${currentGroupId.value}`)
    scrollToBottom()
  } catch (error) {
    console.error('加载群组消息失败:', error)
  }
}

const selectFriend = (friendId) => {
  currentGroupId.value = null
  groupMessages.value = []
  currentFriendId.value = friendId
  loadMessages()
}

const selectGroup = (groupId) => {
  currentFriendId.value = null
  messages.value = []
  currentGroupId.value = groupId
  loadGroupMessages()
}

const goBackToList = () => {
  currentFriendId.value = null
  currentGroupId.value = null
  messages.value = []
  groupMessages.value = []
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || sending.value) return

  sending.value = true
  try {
    if (currentFriendId.value) {
      const msg = await api.post('/chat/messages', {
        receiver_id: currentFriendId.value,
        content: inputMessage.value.trim()
      })
      messages.value.push(msg)
      loadConversations()
    } else if (currentGroupId.value) {
      const msg = await api.post('/group-chat/messages', {
        group_id: currentGroupId.value,
        content: inputMessage.value.trim(),
        message_type: 'text'
      })
      groupMessages.value.push(msg)
      loadGroupConversations()
    }
    inputMessage.value = ''
    scrollToBottom()
  } catch (error) {
    console.error('发送消息失败:', error)
  } finally {
    sending.value = false
  }
}

// 发送图片
const sendImage = () => {
  imageInput.value?.click()
}

// 发送文件
const sendFile = () => {
  fileInput.value?.click()
}

// 处理图片选择
const handleImageSelect = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  await uploadChatFile(file)
  event.target.value = ''
}

// 处理文件选择
const handleFileSelect = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  await uploadChatFile(file)
  event.target.value = ''
}

// 上传聊天文件
const uploadChatFile = async (file) => {
  if (!currentGroupId.value && !currentFriendId.value) return

  sending.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)

    if (currentGroupId.value) {
      formData.append('group_id', currentGroupId.value)
      const msg = await api.post('/group-chat/messages/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      groupMessages.value.push(msg)
      loadGroupConversations()
    } else if (currentFriendId.value) {
      formData.append('receiver_id', currentFriendId.value)
      const msg = await api.post('/chat/messages/file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      messages.value.push(msg)
      loadConversations()
    }
    scrollToBottom()
  } catch (error) {
    console.error('发送文件失败:', error)
  } finally {
    sending.value = false
  }
}

// 下载文件
const downloadFile = (msg) => {
  if (!msg.file_id) return
  const token = localStorage.getItem('token')
  window.open(`/files/api/files/${msg.file_id}/download?token=${token}`, '_blank')
}

const handleFileMessageClick = (msg) => {
  if (canPreviewMessageFile(msg)) {
    previewFile.value = normalizeMessageFile(msg)
    previewUrl.value = buildFilePreviewUrl(msg.file_id)
    showPreviewDialog.value = true
    return
  }
  downloadFile(msg)
}

const fetchPreviewText = async () => {
  const response = await fetch(previewUrl.value)
  if (!response.ok) {
    throw new Error('无法读取文件内容')
  }
  return response.text()
}

const downloadPreviewFile = () => {
  if (previewFile.value?.id) {
    downloadFile({ file_id: previewFile.value.id })
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 处理实时好友消息
const handleWebSocketMessage = (msg) => {
  if (msg.sender_id === currentFriendId.value) {
    messages.value.push({
      id: msg.id,
      sender_id: msg.sender_id,
      receiver_id: msg.receiver_id,
      sender_name: msg.sender_name,
      sender_real_name: msg.sender_real_name,
      message_type: msg.message_type || 'text',
      content: msg.content,
      file_id: msg.file_id,
      file_name: msg.file_name,
      file_size: msg.file_size,
      is_read: true,
      created_at: msg.created_at
    })
    scrollToBottom()
    const conv = conversations.value.find(c => c.user_id === msg.sender_id)
    if (conv && conv.unread_count > 0) {
      const prevUnread = conv.unread_count
      conv.unread_count = 0
      chatStore.decreaseUnread(prevUnread)
    }
  } else if (msg.receiver_id === currentFriendId.value) {
    messages.value.push({
      id: msg.id,
      sender_id: msg.sender_id,
      receiver_id: msg.receiver_id,
      sender_name: msg.sender_name,
      sender_real_name: msg.sender_real_name,
      message_type: msg.message_type || 'text',
      content: msg.content,
      file_id: msg.file_id,
      file_name: msg.file_name,
      file_size: msg.file_size,
      is_read: true,
      created_at: msg.created_at
    })
    scrollToBottom()
  }
  loadConversations()
}

// 处理实时群组消息
const handleGroupWebSocketMessage = (msg) => {
  if (msg.group_id === currentGroupId.value) {
    groupMessages.value.push({
      id: msg.id,
      group_id: msg.group_id,
      sender_id: msg.sender_id,
      sender_name: msg.sender_name,
      sender_real_name: msg.sender_real_name,
      message_type: msg.message_type || 'text',
      content: msg.content,
      file_id: msg.file_id,
      file_name: msg.file_name,
      file_size: msg.file_size,
      created_at: msg.created_at
    })
    scrollToBottom()
  }
  loadGroupConversations()
}

onMounted(async () => {
  if (route.query.friendId) {
    currentFriendId.value = parseInt(route.query.friendId)
  }
  if (route.query.groupId) {
    currentGroupId.value = parseInt(route.query.groupId)
    activeTab.value = 'groups'
  }

  await loadConversations()
  await loadGroupConversations()

  if (currentFriendId.value) {
    await loadMessages()
  }
  if (currentGroupId.value) {
    await loadGroupMessages()
  }

  notificationService.on('chat_message', handleWebSocketMessage)
  notificationService.on('group_chat_message', handleGroupWebSocketMessage)
})

onUnmounted(() => {
  notificationService.off('chat_message', handleWebSocketMessage)
  notificationService.off('group_chat_message', handleGroupWebSocketMessage)
})

watch(currentFriendId, async (newId) => {
  if (newId) {
    const conv = conversations.value.find(c => c.user_id === newId)
    const prevUnread = conv?.unread_count || 0
    await loadMessages()
    if (conv && prevUnread > 0) {
      conv.unread_count = 0
      chatStore.decreaseUnread(prevUnread)
    }
  }
})

watch(currentGroupId, async (newId) => {
  if (newId) {
    await loadGroupMessages()
  }
})

watch(showInviteDialog, (newVal) => {
  if (newVal) {
    loadInviteFriends()
  }
})
</script>

<style scoped>
.chat-page {
  height: calc(100vh - 120px);
}

.chat-container {
  height: 100%;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 22px;
  overflow: hidden;
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
  border: 1px solid rgba(218, 229, 247, 0.92);
  backdrop-filter: blur(20px);
  display: flex;
}

.conversation-list {
  width: 25%;
  min-width: 280px;
  border-right: 1px solid rgba(224, 233, 248, 0.75);
  display: flex;
  flex-direction: column;
  height: 100%;
  background: rgba(247, 250, 255, 0.5);
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.back-btn {
  display: none;
  margin-right: 8px;
}

.conversation-header {
  padding: 20px;
  font-size: 16px;
  font-weight: 800;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-main);
}

.chat-tabs {
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  background: rgba(255, 255, 255, 0.9);
}

.chat-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.chat-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 16px;
}

.chat-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-regular);
}

.chat-tabs :deep(.el-tabs__item.is-active) {
  color: var(--primary);
}

.conversations {
  flex: 1;
  overflow-y: auto;
}

.conversation-item {
  display: flex;
  align-items: center;
  padding: 14px 20px;
  cursor: pointer;
  transition: all 0.2s;
  background: rgba(255, 255, 255, 0.6);
  margin: 4px 8px;
  border-radius: 13px;
}

.conversation-item:hover {
  background: rgba(47, 123, 255, 0.08);
}

.conversation-item.active {
  background: linear-gradient(90deg, rgba(47, 123, 255, 0.16), rgba(47, 123, 255, 0.06));
  box-shadow: inset 3px 0 0 var(--primary);
}

.conv-info {
  flex: 1;
  margin-left: 12px;
  overflow: hidden;
}

.conv-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.conv-last-msg {
  font-size: 12px;
  color: var(--text-light);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 4px;
}

.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  font-size: 16px;
  font-weight: 800;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.9);
}

.chat-title {
  color: var(--text-main);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: linear-gradient(180deg, rgba(248, 249, 251, 0.6) 0%, rgba(240, 242, 245, 0.6) 100%);
}

.message-item {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
}

.message-item.mine {
  flex-direction: row;
  justify-content: flex-end;
}

.avatar {
  flex-shrink: 0;
}

.avatar-mine {
  order: 1;
}

.message-content {
  max-width: 60%;
  min-width: 0;
}

.sender-name {
  font-size: 12px;
  color: var(--text-light);
  margin-bottom: 6px;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  word-break: break-word;
  box-shadow: 0 4px 16px rgba(70, 102, 155, 0.08);
  font-size: 14px;
  line-height: 1.5;
  border: 1px solid rgba(218, 229, 247, 0.6);
}

.message-item.mine .message-bubble {
  background: linear-gradient(135deg, #6ba3ff, #5b9aff);
  color: #fff;
  border: none;
  box-shadow: 0 6px 16px rgba(91, 154, 255, 0.25);
}

.image-bubble {
  padding: 4px;
}

.chat-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 12px;
  cursor: pointer;
}

.image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 150px;
  height: 100px;
  background: rgba(247, 250, 255, 0.8);
  border-radius: 12px;
  color: var(--text-light);
}

.file-bubble {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
  cursor: pointer;
  transition: background 0.2s;
  border-radius: 12px;
  padding: 4px;
}

.file-bubble:hover {
  background: rgba(47, 123, 255, 0.06);
}

.message-item.mine .file-bubble:hover {
  background: rgba(255, 255, 255, 0.15);
}

.file-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-item.mine .file-icon-wrapper {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: var(--text-light);
  margin-top: 2px;
}

.message-item.mine .file-size {
  color: rgba(255, 255, 255, 0.8);
}

.download-icon {
  color: var(--text-light);
}

.message-item.mine .download-icon {
  color: rgba(255, 255, 255, 0.8);
}

.message-time {
  font-size: 11px;
  color: #b0b0b0;
  margin-top: 6px;
}

.message-item.mine .message-time {
  text-align: right;
}

.input-area {
  padding: 16px 20px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
  background: rgba(255, 255, 255, 0.9);
}

.input-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.no-chat-selected {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-light);
  background: rgba(248, 249, 251, 0.6);
}

.no-messages {
  text-align: center;
  color: var(--text-light);
  padding: 40px;
}

.unread-badge {
  margin-left: 8px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.invite-friend-list {
  max-height: 400px;
  overflow-y: auto;
}

.invite-friend-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  transition: background 0.2s;
}

.invite-friend-item:last-child {
  border-bottom: none;
}

.invite-friend-item:hover {
  background: rgba(47, 123, 255, 0.06);
  border-radius: 13px;
}

.friend-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.friend-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

:deep(.el-dialog) {
  border-radius: 22px;
}

:deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
}

:deep(.el-dialog__title) {
  font-weight: 800;
  color: var(--text-main);
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
}

@media screen and (max-width: 768px) {
  .chat-page {
    height: calc(100vh - 80px);
  }

  .chat-container {
    border-radius: 0;
  }

  .conversation-list {
    width: 100%;
    min-width: unset;
  }

  .conversation-list.mobile-hidden {
    display: none;
  }

  .chat-area {
    display: none;
  }

  .chat-area.mobile-visible {
    display: flex;
  }

  .back-btn {
    display: flex;
  }

  .chat-header {
    padding: 12px 16px;
  }

  .chat-title {
    flex: 1;
  }

  .message-content {
    max-width: 75%;
  }

  .chat-image {
    max-width: 150px;
    max-height: 150px;
  }

  .file-bubble {
    min-width: 150px;
  }

  .input-area {
    padding: 12px 16px;
  }

  .conv-name {
    font-size: 15px;
  }

  .conversation-header {
    padding: 12px 16px;
  }
}
</style>
