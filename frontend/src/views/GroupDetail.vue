<template>
  <div class="group-detail">
    <el-page-header @back="goBack" title="群组管理">
      <template #content>
        <span class="group-title">{{ isNew ? '创建群组' : group.name }}</span>
      </template>
    </el-page-header>

    <el-divider />

    <!-- 创建群组表单 -->
    <el-card v-if="isNew">
      <el-form :model="groupForm" label-width="100px" style="max-width: 500px">
        <el-form-item label="群组名称" required>
          <el-input v-model="groupForm.name" placeholder="请输入群组名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="groupForm.description" type="textarea" :rows="3" placeholder="请输入群组描述" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createGroup" :loading="saving">创建群组</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 群组详情 - QQ风格聊天界面 -->
    <template v-else>
      <div class="qq-chat-container">
        <!-- 左侧聊天区域 -->
        <div class="chat-main">
          <!-- 聊天头部 -->
          <div class="chat-header">
            <div class="chat-title-info">
              <span class="chat-name">{{ group.name }}</span>
              <span class="chat-member-count">({{ members.length }}人)</span>
            </div>
            <div class="chat-actions">
              <el-button type="primary" text @click="showMemberPanel = !showMemberPanel">
                <el-icon><User /></el-icon>
                成员
              </el-button>
              <el-button type="primary" text @click="showGroupFiles">
                <el-icon><Folder /></el-icon>
                文件
              </el-button>
              <el-button type="primary" text @click="showSettingsDialog = true">
                <el-icon><Setting /></el-icon>
                设置
              </el-button>
            </div>
          </div>

          <!-- 消息列表 -->
          <div class="message-list" ref="messageListRef">
            <div
              v-for="msg in messages"
              :key="msg.id"
              :class="['message-item', { mine: msg.sender_id === currentUserId }]"
            >
              <!-- 时间分隔 -->
              <div class="time-divider" v-if="shouldShowTime(msg)">
                {{ formatDateTime(msg.created_at) }}
              </div>

              <div class="message-wrapper">
                <!-- 头像 -->
                <el-avatar
                  :size="40"
                  :class="['avatar', { 'avatar-mine': msg.sender_id === currentUserId }]"
                >
                  {{ (msg.sender_real_name || msg.sender_name || '?').charAt(0).toUpperCase() }}
                </el-avatar>

                <!-- 消息内容 -->
                <div class="message-body">
                  <div class="sender-info" v-if="msg.sender_id !== currentUserId">
                    <span class="sender-name">{{ msg.sender_real_name || msg.sender_name }}</span>
                  </div>

                  <!-- 文本消息 -->
                  <div v-if="msg.message_type === 'text'" class="message-bubble text-message">
                    {{ msg.content }}
                  </div>

                  <!-- 图片消息 -->
                  <div v-else-if="msg.message_type === 'image'" class="message-bubble image-message" @click="previewImage(msg)">
                    <el-image
                      :src="getFileUrl(msg.file_id)"
                      fit="cover"
                      :preview-src-list="[getFileUrl(msg.file_id)]"
                      class="chat-image"
                    >
                      <template #error>
                        <div class="image-placeholder">
                          <el-icon><Picture /></el-icon>
                          <span>图片加载失败</span>
                        </div>
                      </template>
                    </el-image>
                  </div>

                  <!-- 文件消息 -->
                  <div v-else-if="msg.message_type === 'file'" class="message-bubble file-message" @click="downloadFile(msg)">
                    <div class="file-icon">
                      <el-icon :size="32"><Document /></el-icon>
                    </div>
                    <div class="file-info">
                      <div class="file-name">{{ msg.file_name }}</div>
                      <div class="file-size">{{ formatFileSize(msg.file_size) }}</div>
                    </div>
                    <el-icon class="download-icon"><Download /></el-icon>
                  </div>

                  <div class="message-time">{{ formatTime(msg.created_at) }}</div>
                </div>
              </div>
            </div>

            <div v-if="messages.length === 0" class="no-messages">
              <el-empty description="暂无消息，发送一条消息开始聊天吧" :image-size="100" />
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-toolbar">
              <el-tooltip content="发送图片">
                <el-button circle @click="sendImage">
                  <el-icon><Picture /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="发送文件">
                <el-button circle @click="sendFile">
                  <el-icon><Document /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
            <div class="input-box">
              <el-input
                v-model="inputMessage"
                type="textarea"
                :rows="3"
                placeholder="输入消息... (Ctrl+Enter发送)"
                @keydown.ctrl.enter="sendMessage"
                :disabled="sending"
              />
            </div>
            <div class="input-footer">
              <el-button type="primary" @click="sendMessage" :loading="sending">
                发送
              </el-button>
            </div>
          </div>

          <!-- 隐藏的文件上传 -->
          <input type="file" ref="imageInput" @change="handleImageSelect" accept="image/*" style="display: none" />
          <input type="file" ref="fileInput" @change="handleFileSelect" style="display: none" />
        </div>

        <!-- 右侧成员面板 -->
        <transition name="slide">
          <div class="member-panel" v-show="showMemberPanel">
            <div class="panel-header">
              <span>群成员 ({{ members.length }})</span>
              <el-button type="primary" size="small" @click="showInviteDialog = true" v-if="canManage">
                邀请
              </el-button>
            </div>
            <div class="member-list">
              <div v-for="member in members" :key="member.user_id" class="member-item">
                <el-avatar :size="36">
                  {{ (member.real_name || member.username || '?').charAt(0).toUpperCase() }}
                </el-avatar>
                <div class="member-info">
                  <div class="member-name">{{ member.real_name || member.username }}</div>
                  <el-tag size="small" :type="getRoleType(member.role)">
                    {{ getRoleName(member.role) }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </transition>
      </div>
    </template>

    <!-- 编辑群组对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑群组" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="群组名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="updateGroupInfo" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 群组设置对话框 -->
    <el-dialog v-model="showSettingsDialog" title="群组设置" width="600px">
      <el-tabs>
        <el-tab-pane label="基本信息">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="群组名称">{{ group.name }}</el-descriptions-item>
            <el-descriptions-item label="描述">{{ group.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="成员数">{{ group.member_count || 0 }}</el-descriptions-item>
            <el-descriptions-item label="公开加入">
              <el-switch v-model="group.is_public_join" @change="updateGroup" :disabled="!canManage" />
            </el-descriptions-item>
          </el-descriptions>

          <!-- 邀请链接区域 -->
          <div class="invite-section" v-if="canManage && group.invite_code">
            <div class="invite-section-title">邀请链接</div>
            <div class="invite-link-display">
              <el-input :model-value="getInviteLink()" readonly size="small">
                <template #append>
                  <el-button size="small" @click="copyGroupInviteLink">复制</el-button>
                </template>
              </el-input>
            </div>
            <div class="invite-code-text">
              邀请码: <strong>{{ group.invite_code }}</strong>
            </div>
          </div>

          <div style="margin-top: 16px" v-if="canManage">
            <el-button type="primary" @click="showEditDialog = true">编辑群组</el-button>
            <el-button type="danger" @click="dissolveGroup" v-if="isOwner">解散群组</el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="成员管理" v-if="canManage">
          <el-table :data="members" size="small">
            <el-table-column label="用户名" prop="username" />
            <el-table-column label="姓名" prop="real_name" />
            <el-table-column label="角色" width="120">
              <template #default="{ row }">
                <el-select
                  v-model="row.role"
                  size="small"
                  @change="updateRole(row)"
                  :disabled="row.role === 'owner'"
                >
                  <el-option label="管理员" value="manager" />
                  <el-option label="成员" value="member" />
                  <el-option label="访客" value="viewer" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="danger"
                  text
                  @click="kickMember(row)"
                  :disabled="row.role === 'owner'"
                >
                  踢出
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 邀请成员对话框 -->
    <el-dialog v-model="showInviteDialog" title="邀请成员" width="600px">
      <el-tabs v-model="inviteType">
        <el-tab-pane label="邀请链接" name="link">
          <div class="invite-link-section">
            <el-form label-width="80px">
              <el-form-item label="有效期">
                <el-select v-model="inviteExpireDays" style="width: 150px">
                  <el-option label="1天" :value="1" />
                  <el-option label="7天" :value="7" />
                  <el-option label="14天" :value="14" />
                  <el-option label="30天" :value="30" />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="generateInviteLink" :loading="generatingLink">
                  生成邀请链接
                </el-button>
              </el-form-item>
            </el-form>

            <div v-if="inviteLink" class="invite-link-box">
              <el-input v-model="inviteLink" readonly>
                <template #append>
                  <el-button @click="copyInviteLink">复制</el-button>
                </template>
              </el-input>
              <div class="invite-info">
                <p>邀请码: <strong>{{ inviteCode }}</strong></p>
                <p>有效期: {{ inviteExpireDays }}天</p>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="邀请好友" name="user">
          <el-alert
            v-if="!userStore.isAdmin"
            type="info"
            :closable="false"
            style="margin-bottom: 16px"
          >
            只能邀请已添加的好友，<router-link to="/friends">前往添加好友</router-link>
          </el-alert>
          <el-form label-width="80px">
            <el-form-item label="选择用户">
              <el-select
                v-model="selectedUserIds"
                multiple
                filterable
                :placeholder="userStore.isAdmin ? '请选择要邀请的用户' : '请选择要邀请的好友'"
                style="width: 100%"
              >
                <el-option
                  v-for="user in availableUsers"
                  :key="user.id"
                  :label="user.real_name || user.username"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-form>
          <el-empty v-if="availableUsers.length === 0" :description="userStore.isAdmin ? '暂无可邀请的用户' : '暂无好友可邀请'" />
        </el-tab-pane>
      </el-tabs>

      <template #footer>
        <el-button @click="showInviteDialog = false">取消</el-button>
        <el-button
          v-if="inviteType === 'user'"
          type="primary"
          @click="sendBatchInvite"
          :loading="inviting"
          :disabled="selectedUserIds.length === 0"
        >
          发送邀请 ({{ selectedUserIds.length }}人)
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Folder, Setting, Picture, Document, Download } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'
import { notificationService } from '@/utils/notifications'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const isNew = computed(() => route.name === 'GroupCreate')
const groupId = computed(() => parseInt(route.params.id))

const group = ref({})
const members = ref([])
const users = ref([])
const loadingMembers = ref(false)
const saving = ref(false)
const inviting = ref(false)
const generatingLink = ref(false)
const showEditDialog = ref(false)
const showInviteDialog = ref(false)
const showSettingsDialog = ref(false)
const showMemberPanel = ref(true)
const inviteType = ref('link')
const selectedUserIds = ref([])
const inviteExpireDays = ref(7)
const inviteLink = ref('')
const inviteCode = ref('')

// 聊天相关
const messages = ref([])
const inputMessage = ref('')
const sending = ref(false)
const messageListRef = ref(null)
const imageInput = ref(null)
const fileInput = ref(null)
const lastMessageTime = ref(null)

const currentUserId = computed(() => userStore.user?.id)

const groupForm = ref({
  name: '',
  description: ''
})

const editForm = ref({
  name: '',
  description: ''
})

const isOwner = computed(() => group.value.owner_id === userStore.user?.id)
const canManage = computed(() => isOwner.value || members.value.find(m => m.user_id === userStore.user?.id)?.role === 'manager')

const getInviteLink = () => {
  if (!group.value.invite_code) return ''
  return `${window.location.origin}/join/${group.value.invite_code}`
}

const copyGroupInviteLink = async () => {
  const link = getInviteLink()
  try {
    await navigator.clipboard.writeText(link)
    ElMessage.success('邀请链接已复制')
  } catch (error) {
    const input = document.createElement('input')
    input.value = link
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    ElMessage.success('邀请链接已复制')
  }
}

const goBack = () => {
  router.push('/groups')
}

const getRoleType = (role) => {
  const map = { 'owner': 'danger', 'manager': 'warning', 'member': '', 'viewer': 'info' }
  return map[role] || 'info'
}

const getRoleName = (role) => {
  const map = { 'owner': '群主', 'manager': '管理员', 'member': '成员', 'viewer': '访客' }
  return map[role] || role
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()

  if (isToday) {
    return formatTime(dateStr)
  } else {
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
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

const shouldShowTime = (msg) => {
  if (!lastMessageTime.value) {
    lastMessageTime.value = msg.created_at
    return true
  }
  const diff = new Date(msg.created_at) - new Date(lastMessageTime.value)
  if (diff > 5 * 60 * 1000) { // 超过5分钟显示时间
    lastMessageTime.value = msg.created_at
    return true
  }
  return false
}

const getFileUrl = (fileId) => {
  if (!fileId) return ''
  return `/api/files/${fileId}/download`
}

const loadGroup = async () => {
  if (isNew.value) return
  try {
    group.value = await api.get(`/groups/${groupId.value}`)
    editForm.value = {
      name: group.value.name,
      description: group.value.description || ''
    }
  } catch (error) {
    ElMessage.error('加载群组信息失败')
  }
}

const loadMembers = async () => {
  if (isNew.value) return
  loadingMembers.value = true
  try {
    members.value = await api.get(`/groups/${groupId.value}/members`)
  } catch (error) {
    console.error('加载成员列表失败:', error)
  } finally {
    loadingMembers.value = false
  }
}

const loadUsers = async () => {
  try {
    users.value = await api.get('/users/simple')
  } catch (error) {
    console.error('加载用户列表失败:', error)
  }
}

// 加载群组消息
const loadMessages = async () => {
  if (isNew.value) return
  try {
    messages.value = await api.get(`/group-chat/messages/${groupId.value}`)
    scrollToBottom()
  } catch (error) {
    console.error('加载消息失败:', error)
  }
}

// 发送文本消息
const sendMessage = async () => {
  if (!inputMessage.value.trim() || sending.value) return

  sending.value = true
  try {
    const msg = await api.post('/group-chat/messages', {
      group_id: groupId.value,
      content: inputMessage.value.trim(),
      message_type: 'text'
    })
    messages.value.push(msg)
    inputMessage.value = ''
    scrollToBottom()
  } catch (error) {
    ElMessage.error('发送消息失败')
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

  await uploadAndSendFile(file, 'image')
  event.target.value = ''
}

// 处理文件选择
const handleFileSelect = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  await uploadAndSendFile(file, 'file')
  event.target.value = ''
}

// 上传并发送文件
const uploadAndSendFile = async (file, type) => {
  sending.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('group_id', groupId.value)

    const msg = await api.post('/group-chat/messages/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    messages.value.push(msg)
    scrollToBottom()
  } catch (error) {
    ElMessage.error('发送文件失败')
  } finally {
    sending.value = false
  }
}

// 下载文件
const downloadFile = async (msg) => {
  if (!msg.file_id) return
  window.open(`/api/files/${msg.file_id}/download`, '_blank')
}

// 预览图片
const previewImage = (msg) => {
  // el-image 组件已内置预览功能
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 查看群组文件
const showGroupFiles = () => {
  router.push(`/spaces?group=${groupId.value}`)
}

// 处理实时群组消息
const handleGroupWebSocketMessage = (msg) => {
  if (msg.group_id === groupId.value) {
    messages.value.push(msg)
    scrollToBottom()
  }
}

const createGroup = async () => {
  if (!groupForm.value.name) {
    ElMessage.warning('请输入群组名称')
    return
  }
  saving.value = true
  try {
    const result = await api.post('/groups', groupForm.value)
    ElMessage.success('群组创建成功')
    router.push(`/groups/${result.id}`)
  } catch (error) {
    ElMessage.error('创建群组失败')
  } finally {
    saving.value = false
  }
}

const updateGroup = async () => {
  saving.value = true
  try {
    await api.put(`/groups/${groupId.value}`, {
      is_public_join: group.value.is_public_join
    })
    ElMessage.success('设置已更新')
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    saving.value = false
  }
}

const updateGroupInfo = async () => {
  saving.value = true
  try {
    await api.put(`/groups/${groupId.value}`, editForm.value)
    group.value.name = editForm.value.name
    group.value.description = editForm.value.description
    showEditDialog.value = false
    ElMessage.success('群组信息已更新')
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    saving.value = false
  }
}

const updateRole = async (member) => {
  try {
    await api.patch(`/groups/${groupId.value}/members/${member.user_id}/role?role=${member.role}`)
    ElMessage.success('角色已更新')
  } catch (error) {
    ElMessage.error('更新角色失败')
    loadMembers()
  }
}

const kickMember = async (member) => {
  try {
    await ElMessageBox.confirm(`确定要踢出 "${member.username}" 吗？`, '提示', { type: 'warning' })
    await api.post(`/groups/${groupId.value}/kick/${member.user_id}`)
    ElMessage.success('已踢出成员')
    loadMembers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('踢出失败')
    }
  }
}

const availableUsers = computed(() => {
  const memberIds = members.value.map(m => m.user_id)
  return users.value.filter(u => !memberIds.includes(u.id))
})

const generateInviteLink = async () => {
  generatingLink.value = true
  try {
    const result = await api.get(`/invitations/link/${groupId.value}`, {
      params: { expire_days: inviteExpireDays.value }
    })
    inviteLink.value = result.invite_link
    inviteCode.value = result.invite_code
    ElMessage.success('邀请链接已生成')
  } catch (error) {
    ElMessage.error('生成邀请链接失败')
  } finally {
    generatingLink.value = false
  }
}

const copyInviteLink = async () => {
  try {
    await navigator.clipboard.writeText(inviteLink.value)
    ElMessage.success('邀请链接已复制到剪贴板')
  } catch (error) {
    const input = document.createElement('input')
    input.value = inviteLink.value
    document.body.appendChild(input)
    input.select()
    document.execCommand('copy')
    document.body.removeChild(input)
    ElMessage.success('邀请链接已复制')
  }
}

const sendBatchInvite = async () => {
  if (selectedUserIds.value.length === 0) {
    ElMessage.warning('请选择要邀请的用户')
    return
  }
  inviting.value = true
  try {
    const result = await api.post('/invitations/batch', {
      group_id: groupId.value,
      invitee_ids: selectedUserIds.value,
      expire_days: inviteExpireDays.value
    })
    if (result.failed_count > 0) {
      ElMessage.warning(`成功邀请 ${result.success_count} 人，${result.failed_count} 人邀请失败`)
    } else {
      ElMessage.success(`已成功邀请 ${result.success_count} 人`)
    }
    selectedUserIds.value = []
    showInviteDialog.value = false
    loadMembers()
  } catch (error) {
    ElMessage.error('发送邀请失败')
  } finally {
    inviting.value = false
  }
}

const dissolveGroup = async () => {
  try {
    await ElMessageBox.confirm('确定要解散群组吗？此操作不可恢复！', '警告', { type: 'danger' })
    await api.delete(`/groups/${groupId.value}`)
    ElMessage.success('群组已解散')
    router.push('/groups')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('解散失败')
    }
  }
}

onMounted(() => {
  if (!isNew.value) {
    loadGroup()
    loadMembers()
    loadUsers()
    loadMessages()

    notificationService.on('group_chat_message', handleGroupWebSocketMessage)
  }
})

onUnmounted(() => {
  notificationService.off('group_chat_message', handleGroupWebSocketMessage)
})

watch(groupId, (newId) => {
  if (newId && !isNew.value) {
    messages.value = []
    lastMessageTime.value = null
    loadMessages()
  }
})
</script>

<style scoped>
.group-detail {
  padding: 20px;
  height: calc(100vh - 120px);
}

.group-title {
  font-size: 18px;
  font-weight: bold;
}

/* QQ风格聊天容器 */
.qq-chat-container {
  display: flex;
  height: 100%;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* 聊天头部 */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.chat-title-info {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.chat-name {
  font-size: 16px;
  font-weight: 600;
}

.chat-member-count {
  font-size: 12px;
  color: #909399;
}

.chat-actions {
  display: flex;
  gap: 8px;
}

/* 消息列表 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  background: #f5f7fa;
}

.message-item {
  margin-bottom: 16px;
}

.time-divider {
  text-align: center;
  color: #909399;
  font-size: 12px;
  margin: 16px 0;
}

.message-wrapper {
  display: flex;
  gap: 12px;
}

.avatar {
  flex-shrink: 0;
}

.avatar-mine {
  order: 1;
}

.message-body {
  max-width: 60%;
  min-width: 0;
}

.mine .message-body {
  order: 0;
}

.sender-info {
  margin-bottom: 4px;
}

.sender-name {
  font-size: 12px;
  color: #606266;
}

.message-bubble {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fff;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.mine .message-bubble {
  background: #95ec69;
}

.text-message {
  line-height: 1.5;
}

.image-message {
  padding: 4px;
  cursor: pointer;
}

.chat-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 4px;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 150px;
  height: 100px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #909399;
}

.file-message {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 200px;
  cursor: pointer;
  transition: background 0.2s;
}

.file-message:hover {
  background: #f0f0f0;
}

.mine .file-message:hover {
  background: #7ed94e;
}

.file-icon {
  color: #409eff;
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
  color: #909399;
}

.download-icon {
  color: #909399;
}

.message-time {
  font-size: 11px;
  color: #b0b0b0;
  margin-top: 4px;
}

.mine .message-time {
  text-align: right;
}

.no-messages {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

/* 输入区域 */
.input-area {
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

.input-toolbar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.input-box {
  padding: 8px 16px 0;
}

.input-box :deep(.el-textarea__inner) {
  border: none;
  resize: none;
  box-shadow: none;
  padding: 0;
}

.input-footer {
  display: flex;
  justify-content: flex-end;
  padding: 8px 16px;
}

/* 成员面板 */
.member-panel {
  width: 260px;
  border-left: 1px solid #e4e7ed;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 600;
}

.member-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.member-item:hover {
  background: #f5f7fa;
}

.member-info {
  flex: 1;
  min-width: 0;
}

.member-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

/* 邀请相关样式 */
.invite-section {
  margin-top: 16px;
  padding: 16px;
  background: #f0f9eb;
  border-radius: 8px;
}

.invite-section-title {
  font-weight: bold;
  margin-bottom: 12px;
  color: #67c23a;
}

.invite-link-display {
  margin-bottom: 8px;
}

.invite-code-text {
  font-size: 12px;
  color: #606266;
}

.invite-link-section {
  padding: 10px 0;
}

.invite-link-box {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.invite-info {
  margin-top: 12px;
  font-size: 13px;
  color: #606266;
}

.invite-info p {
  margin: 4px 0;
}
</style>
