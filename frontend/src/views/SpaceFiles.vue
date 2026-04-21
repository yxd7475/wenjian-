<template>
  <div class="space-files">
    <el-page-header @back="goBack" :title="spaceInfo.name || '空间'">
      <template #content>
        <span class="space-title">{{ spaceInfo.name || '空间文件' }}</span>
      </template>
      <template #extra>
        <el-tag :type="getSpaceTypeTag(spaceInfo.space_type)" size="small">
          {{ getSpaceTypeName(spaceInfo.space_type) }}
        </el-tag>
      </template>
    </el-page-header>

    <el-divider />

    <!-- 群组聊天区域 - 仅群组空间显示 -->
    <div v-if="spaceInfo.space_type === 'group'" class="group-chat-section">
      <div class="chat-header">
        <div class="chat-title">
          <el-icon><ChatDotRound /></el-icon>
          <span>群组聊天</span>
          <span class="member-count">({{ memberCount }}人)</span>
        </div>
        <div class="chat-actions">
          <el-button size="small" type="primary" @click="showInviteDialog = true">
            <el-icon><Plus /></el-icon>
            邀请好友
          </el-button>
          <el-button size="small" @click="toggleChat" :type="showChatPanel ? 'primary' : 'default'">
            {{ showChatPanel ? '收起聊天' : '展开聊天' }}
          </el-button>
          <el-button size="small" @click="showMembersDialog = true">
            <el-icon><User /></el-icon>
            成员
          </el-button>
          <el-button size="small" @click="showSettingsDialog = true">
            <el-icon><Setting /></el-icon>
            设置
          </el-button>
        </div>
      </div>

      <!-- 聊天面板 -->
      <transition name="slide-down">
        <div v-show="showChatPanel" class="chat-panel">
          <!-- 消息列表 -->
          <div class="message-list" ref="messageListRef">
            <div
              v-for="msg in messages"
              :key="msg.id"
              :class="['message-item', { mine: msg.sender_id === currentUserId }]"
            >
              <el-avatar :size="32" class="avatar">
                {{ (msg.sender_real_name || msg.sender_name || '?').charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="message-body">
                <div class="sender-name" v-if="msg.sender_id !== currentUserId">
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
                  />
                </div>
                <!-- 文件消息 -->
                <div v-else-if="msg.message_type === 'file'" class="message-bubble file-bubble" @click="downloadFile(msg)">
                  <el-icon><Document /></el-icon>
                  <span class="file-name">{{ msg.file_name }}</span>
                  <span class="file-size">{{ formatFileSize(msg.file_size) }}</span>
                  <el-icon class="download-icon"><Download /></el-icon>
                </div>
                <div class="message-time">{{ formatTime(msg.created_at) }}</div>
              </div>
            </div>
            <div v-if="messages.length === 0" class="no-messages">
              暂无消息，发送一条消息开始聊天吧
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="input-area">
            <div class="input-toolbar">
              <el-button circle size="small" @click="sendImage" title="发送图片">
                <el-icon><Picture /></el-icon>
              </el-button>
              <el-button circle size="small" @click="sendFile" title="发送文件">
                <el-icon><Folder /></el-icon>
              </el-button>
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
        </div>
      </transition>
    </div>

    <el-divider v-if="spaceInfo.space_type === 'group'" />

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon> 上传文件
        </el-button>
        <el-button @click="createFolder">
          <el-icon><FolderAdd /></el-icon> 新建文件夹
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文件"
          style="width: 200px"
          clearable
          @keyup.enter="searchFiles"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
    </div>

    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin: 16px 0">
      <el-breadcrumb-item :to="{ path: `/space/${spaceId}` }">根目录</el-breadcrumb-item>
      <el-breadcrumb-item
        v-for="folder in breadcrumb"
        :key="folder.id"
        :to="{ path: `/space/${spaceId}`, query: { folder: folder.id } }"
      >
        {{ folder.name }}
      </el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 文件列表 -->
    <el-table :data="fileList" v-loading="loading" @row-click="handleRowClick">
      <el-table-column label="名称" min-width="300">
        <template #default="{ row }">
          <div class="file-name">
            <el-icon :size="24" :color="getFileIconColor(row)">
              <component :is="getFileIcon(row)" />
            </el-icon>
            <span style="margin-left: 8px">{{ row.origin_name || row.name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="120">
        <template #default="{ row }">
          {{ row.is_folder ? '-' : formatSize(row.size) }}
        </template>
      </el-table-column>
      <el-table-column label="修改时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at || row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="downloadFileItem(row)" v-if="!row.is_folder">
            下载
          </el-button>
          <el-button size="small" @click.stop="openFolder(row)" v-if="row.is_folder">
            打开
          </el-button>
          <el-button size="small" type="primary" @click.stop="openShareDialog(row)" v-if="!row.is_folder">
            分享
          </el-button>
          <el-button size="small" type="danger" @click.stop="deleteItem(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @size-change="loadFiles"
      @current-change="loadFiles"
    />

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传文件" width="500px">
      <el-upload
        drag
        multiple
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处或<em>点击上传</em></div>
      </el-upload>
    </el-dialog>

    <!-- 成员对话框 -->
    <el-dialog v-model="showMembersDialog" title="群组成员" width="500px">
      <el-table :data="members" size="small">
        <el-table-column label="用户名" prop="username" />
        <el-table-column label="姓名" prop="real_name" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)" size="small">
              {{ getRoleName(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 设置对话框 -->
    <el-dialog v-model="showSettingsDialog" title="群组设置" width="600px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="群组名称">{{ groupInfo.name }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ groupInfo.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="成员数">{{ memberCount }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 16px">
        <el-button type="primary" @click="goToGroupDetail">管理群组</el-button>
      </div>
    </el-dialog>

    <!-- 分享对话框 -->
    <el-dialog v-model="showShareDialog" title="分享文件" width="500px">
      <el-form :model="shareForm" label-width="100px">
        <el-form-item label="文件名">
          <el-input :value="shareTarget?.origin_name" disabled />
        </el-form-item>
        <el-form-item label="访问密码">
          <el-input v-model="shareForm.password" placeholder="留空则不需要密码" clearable />
        </el-form-item>
        <el-form-item label="有效期">
          <el-select v-model="shareForm.expire_hours" style="width: 100%">
            <el-option label="1小时" :value="1" />
            <el-option label="6小时" :value="6" />
            <el-option label="24小时" :value="24" />
            <el-option label="3天" :value="72" />
            <el-option label="7天" :value="168" />
            <el-option label="永不过期" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="下载次数">
          <el-input-number v-model="shareForm.max_downloads" :min="0" style="width: 100%" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px">0表示不限制下载次数</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showShareDialog = false">取消</el-button>
        <el-button type="primary" @click="createShare" :loading="shareCreating">创建分享</el-button>
      </template>
    </el-dialog>

    <!-- 分享结果对话框 -->
    <el-dialog v-model="showShareResult" title="分享成功" width="500px">
      <el-form label-width="100px">
        <el-form-item label="分享链接">
          <div style="display: flex; gap: 8px;">
            <el-input :value="shareLink" readonly style="flex: 1" />
            <el-button type="primary" @click="copyShareLink">复制</el-button>
          </div>
        </el-form-item>
        <el-form-item label="访问密码" v-if="shareResult?.password">
          <el-input :value="shareResult.password" readonly />
        </el-form-item>
        <el-form-item label="过期时间" v-if="shareResult?.expire_at">
          {{ formatDate(shareResult.expire_at) }}
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" style="margin-top: 10px">
        分享链接可被任何人访问，无需登录账号
      </el-alert>
      <template #footer>
        <el-button type="primary" @click="showShareResult = false">确定</el-button>
      </template>
    </el-dialog>

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
          <el-button type="primary" size="small" @click="inviteFriend(friend.id)" :loading="invitingFriendId === friend.id">
            邀请
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, User, Setting, Picture, Folder, Document, Download, Plus, Loading } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { notificationService } from '@/utils/notifications'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const spaceId = computed(() => parseInt(route.params.id))
const currentFolderId = computed(() => route.query.folder ? parseInt(route.query.folder) : null)
const currentUserId = computed(() => userStore.user?.id)

const spaceInfo = ref({})
const groupInfo = ref({})
const members = ref([])
const files = ref([])
const folders = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const breadcrumb = ref([])
const showUploadDialog = ref(false)
const showMembersDialog = ref(false)
const showSettingsDialog = ref(false)

// 邀请好友相关
const showInviteDialog = ref(false)
const inviteFriends = ref([])
const inviteLoading = ref(false)
const invitingFriendId = ref(null)

// 聊天相关
const showChatPanel = ref(true)
const messages = ref([])
const inputMessage = ref('')
const sending = ref(false)
const messageListRef = ref(null)
const imageInput = ref(null)
const fileInput = ref(null)

// 分享相关
const showShareDialog = ref(false)
const showShareResult = ref(false)
const shareTarget = ref(null)
const shareCreating = ref(false)
const shareResult = ref(null)
const shareForm = ref({
  password: '',
  expire_hours: 24,
  max_downloads: 0
})

const shareLink = computed(() => {
  if (!shareResult.value) return ''
  let baseUrl = window.location.origin
  if (serverIp.value) {
    baseUrl = `${window.location.protocol}//${serverIp.value}:${window.location.port}`
  }
  return `${baseUrl}/s/${shareResult.value.share_code}`
})

const memberCount = computed(() => members.value.length)

const fileList = computed(() => {
  const folderItems = folders.value.map(f => ({
    ...f,
    is_folder: true,
    origin_name: f.name
  }))
  return [...folderItems, ...files.value]
})

const uploadUrl = computed(() => {
  let url = '/api/files/upload?space_id=' + spaceId.value
  if (currentFolderId.value) {
    url += '&folder_id=' + currentFolderId.value
  }
  return url
})

const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}))

const goBack = () => {
  router.push('/files')
}

const getSpaceTypeName = (type) => {
  const map = {
    'admin': '管理员空间',
    'personal': '个人空间',
    'group': '群组空间'
  }
  return map[type] || type
}

const getSpaceTypeTag = (type) => {
  const map = {
    'admin': 'danger',
    'personal': 'primary',
    'group': 'success'
  }
  return map[type] || 'info'
}

const getRoleType = (role) => {
  const map = { 'owner': 'danger', 'manager': 'warning', 'member': '', 'viewer': 'info' }
  return map[role] || 'info'
}

const getRoleName = (role) => {
  const map = { 'owner': '群主', 'manager': '管理员', 'member': '成员', 'viewer': '访客' }
  return map[role] || role
}

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatTime = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()
  if (isToday) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

const getFileIcon = (row) => {
  if (row.is_folder) return 'Folder'
  const ext = row.ext?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext)) return 'Picture'
  if (['pdf'].includes(ext)) return 'Document'
  if (['doc', 'docx'].includes(ext)) return 'Document'
  if (['xls', 'xlsx'].includes(ext)) return 'Grid'
  if (['mp3', 'wav', 'flac'].includes(ext)) return 'Headset'
  if (['mp4', 'avi', 'mov'].includes(ext)) return 'VideoPlay'
  if (['zip', 'rar', '7z'].includes(ext)) return 'Files'
  return 'Document'
}

const getFileIconColor = (row) => {
  if (row.is_folder) return '#E6A23C'
  const ext = row.ext?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(ext)) return '#67C23A'
  if (['pdf'].includes(ext)) return '#F56C6C'
  if (['doc', 'docx'].includes(ext)) return '#409EFF'
  if (['xls', 'xlsx'].includes(ext)) return '#67C23A'
  return '#909399'
}

const getFileUrl = (fileId) => {
  if (!fileId) return ''
  const token = localStorage.getItem('token')
  return `/api/files/${fileId}/download?token=${token}`
}

const toggleChat = () => {
  showChatPanel.value = !showChatPanel.value
}

const goToGroupDetail = () => {
  if (groupInfo.value.id) {
    router.push(`/groups/${groupInfo.value.id}`)
  }
}

// 加载空间信息
const loadSpaceInfo = async () => {
  try {
    spaceInfo.value = await api.get(`/spaces/${spaceId.value}`)

    // 如果是群组空间，加载群组信息和聊天
    if (spaceInfo.value.space_type === 'group' && spaceInfo.value.group_id) {
      await loadGroupInfo()
      await loadMembers()
      await loadMessages()
    }
  } catch (error) {
    console.error('加载空间信息失败:', error)
  }
}

// 加载群组信息
const loadGroupInfo = async () => {
  try {
    groupInfo.value = await api.get(`/groups/${spaceInfo.value.group_id}`)
  } catch (error) {
    console.error('加载群组信息失败:', error)
  }
}

// 加载成员
const loadMembers = async () => {
  try {
    members.value = await api.get(`/groups/${spaceInfo.value.group_id}/members`)
  } catch (error) {
    console.error('加载成员失败:', error)
  }
}

// 加载消息
const loadMessages = async () => {
  if (!spaceInfo.value.group_id) return
  try {
    messages.value = await api.get(`/group-chat/messages/${spaceInfo.value.group_id}`)
    scrollToBottom()
  } catch (error) {
    console.error('加载消息失败:', error)
  }
}

// 发送消息
const sendMessage = async () => {
  if (!inputMessage.value.trim() || sending.value) return

  sending.value = true
  try {
    const msg = await api.post('/group-chat/messages', {
      group_id: spaceInfo.value.group_id,
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
  sending.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('group_id', spaceInfo.value.group_id)

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

// 下载聊天文件
const downloadFile = (msg) => {
  if (!msg.file_id) return
  const token = localStorage.getItem('token')
  window.open(`/api/files/${msg.file_id}/download?token=${token}`, '_blank')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 处理实时群组消息
const handleGroupWebSocketMessage = (msg) => {
  if (msg.group_id === spaceInfo.value.group_id) {
    messages.value.push(msg)
    scrollToBottom()
  }
}

const loadFiles = async () => {
  loading.value = true
  try {
    const params = {
      space_id: spaceId.value,
      page: page.value,
      page_size: pageSize.value
    }
    if (currentFolderId.value) {
      params.folder_id = currentFolderId.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }

    const result = await api.get('/files', { params })
    files.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    console.error('加载文件失败:', error)
    ElMessage.error('加载文件失败')
  } finally {
    loading.value = false
  }
}

const loadFolders = async () => {
  try {
    const result = await api.get(`/spaces/${spaceId.value}/folders`, {
      params: { parent_id: currentFolderId.value }
    })
    folders.value = result || []
  } catch (error) {
    console.error('加载文件夹失败:', error)
  }
}

const openFolder = (folder) => {
  router.push({
    path: `/space/${spaceId.value}`,
    query: { folder: folder.id }
  })
}

const handleRowClick = (row) => {
  if (row.is_folder) {
    openFolder(row)
  }
}

const createFolder = async () => {
  try {
    const { value: name } = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /^.{1,255}$/,
      inputErrorMessage: '文件夹名称不能为空'
    })
    await api.post('/files/folders', {
      name,
      parent_id: currentFolderId.value,
      space_id: spaceId.value
    })
    ElMessage.success('文件夹创建成功')
    loadFiles()
    loadFolders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('创建文件夹失败')
    }
  }
}

const downloadFileItem = (file) => {
  const token = localStorage.getItem('token')
  window.open(`/api/files/${file.id}/download?token=${token}`, '_blank')
}

const deleteItem = async (item) => {
  try {
    await ElMessageBox.confirm(`确定要删除 "${item.origin_name || item.name}" 吗？`, '提示', { type: 'warning' })
    if (item.is_folder) {
      await api.delete(`/files/folders/${item.id}`)
    } else {
      await api.delete(`/files/${item.id}`)
    }
    ElMessage.success('删除成功')
    loadFiles()
    loadFolders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 分享相关方法
const openShareDialog = (file) => {
  if (file.is_folder) {
    ElMessage.warning('暂不支持分享文件夹')
    return
  }
  shareTarget.value = file
  shareForm.value = {
    password: '',
    expire_hours: 24,
    max_downloads: 0
  }
  showShareDialog.value = true
}

const createShare = async () => {
  if (!shareTarget.value) return
  shareCreating.value = true
  try {
    shareResult.value = await api.post('/shares', {
      file_id: shareTarget.value.id,
      ...shareForm.value
    })
    await fetchServerIp()
    showShareDialog.value = false
    showShareResult.value = true
  } catch (error) {
    ElMessage.error('创建分享失败')
  } finally {
    shareCreating.value = false
  }
}

const copyShareLink = () => {
  const link = shareLink.value
  console.log('复制链接:', link)

  if (!link) {
    ElMessage.error('分享链接为空')
    return
  }

  // 创建 textarea 元素
  const textarea = document.createElement('textarea')
  textarea.value = link
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()

  let success = false
  try {
    success = document.execCommand('copy')
    console.log('复制结果:', success)
  } catch (e) {
    console.error('复制异常:', e)
  }

  document.body.removeChild(textarea)

  if (success) {
    ElMessage.success('复制成功：' + link)
  } else {
    ElMessage.error('复制失败，请手动复制')
  }
}

const serverIp = ref(null)

const fetchServerIp = async () => {
  if (serverIp.value) return
  try {
    const data = await api.get('/auth/server-info')
    if (data.local_ips && data.local_ips.length > 0) {
      const preferredIp = data.local_ips.find(ip => !ip.startsWith('172.'))
      serverIp.value = preferredIp || data.local_ips[0]
    }
  } catch (error) {
    console.error('获取服务器 IP 失败:', error)
  }
}

// 加载可邀请的好友列表
const loadInviteFriends = async () => {
  if (!spaceInfo.value.group_id) return
  inviteLoading.value = true
  try {
    inviteFriends.value = await api.get(`/groups/${spaceInfo.value.group_id}/invite-friends`)
  } catch (error) {
    console.error('加载好友列表失败:', error)
  } finally {
    inviteLoading.value = false
  }
}

// 邀请好友加入群组
const inviteFriend = async (friendId) => {
  if (!spaceInfo.value.group_id) return
  invitingFriendId.value = friendId
  try {
    await api.post(`/groups/${spaceInfo.value.group_id}/invite/${friendId}`)
    ElMessage.success('邀请成功')
    // 从列表中移除已邀请的好友
    inviteFriends.value = inviteFriends.value.filter(f => f.id !== friendId)
    // 刷新成员列表
    loadMembers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '邀请失败')
  } finally {
    invitingFriendId.value = null
  }
}

const searchFiles = () => {
  page.value = 1
  loadFiles()
}

const handleUploadSuccess = () => {
  ElMessage.success('上传成功')
  showUploadDialog.value = false
  loadFiles()
}

const handleUploadError = () => {
  ElMessage.error('上传失败')
}

watch([spaceId, currentFolderId], () => {
  loadSpaceInfo()
  loadFiles()
  loadFolders()
})

onMounted(() => {
  loadSpaceInfo()
  loadFiles()
  loadFolders()
  fetchServerIp()  // 获取服务器 IP

  // 监听WebSocket消息
  notificationService.on('group_chat_message', handleGroupWebSocketMessage)
})

onUnmounted(() => {
  notificationService.off('group_chat_message', handleGroupWebSocketMessage)
})

watch(showInviteDialog, (newVal) => {
  if (newVal) {
    loadInviteFriends()
  }
})
</script>

<style scoped>
.space-files {
  padding: 20px;
}

.space-title {
  font-size: 18px;
  font-weight: bold;
}

/* 群组聊天区域 */
.group-chat-section {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
}

.member-count {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}

.chat-actions {
  display: flex;
  gap: 8px;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  max-height: 350px;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  min-height: 150px;
  max-height: 250px;
  background: #fafafa;
}

.message-item {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}

.message-item.mine {
  flex-direction: row-reverse;
}

.avatar {
  flex-shrink: 0;
}

.message-body {
  max-width: 60%;
  min-width: 0;
}

.sender-name {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
}

.message-item.mine .sender-name {
  text-align: right;
}

.message-bubble {
  padding: 8px 12px;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  line-height: 1.4;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.message-item.mine .message-bubble {
  background: #95ec69;
}

.image-bubble {
  padding: 4px;
}

.chat-image {
  max-width: 150px;
  max-height: 150px;
  border-radius: 4px;
  cursor: pointer;
}

.file-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  min-width: 180px;
}

.file-bubble:hover {
  background: #f0f0f0;
}

.message-item.mine .file-bubble:hover {
  background: #7ed94e;
}

.file-bubble .file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.file-bubble .file-size {
  font-size: 12px;
  color: #909399;
}

.download-icon {
  color: #909399;
  font-size: 16px;
}

.message-time {
  font-size: 11px;
  color: #b0b0b0;
  margin-top: 4px;
}

.message-item.mine .message-time {
  text-align: right;
}

.no-messages {
  text-align: center;
  color: #909399;
  padding: 30px;
}

.input-area {
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
  background: #fff;
}

.input-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
  max-height: 350px;
}

.slide-down-enter-from,
.slide-down-leave-to {
  max-height: 0;
  opacity: 0;
}

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.file-name {
  display: flex;
  align-items: center;
  cursor: pointer;
}

/* 手机端适配 */
@media screen and (max-width: 768px) {
  .space-files {
    padding: 10px;
  }

  .space-title {
    font-size: 16px;
  }

  .el-page-header {
    flex-wrap: wrap;
  }

  /* 群组聊天区域 */
  .group-chat-section {
    border-radius: 4px;
  }

  .chat-header {
    flex-wrap: wrap;
    padding: 10px 12px;
    gap: 8px;
  }

  .chat-title {
    font-size: 14px;
  }

  .chat-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .chat-actions .el-button {
    padding: 5px 10px;
    font-size: 12px;
  }

  .chat-panel {
    max-height: 300px;
  }

  .message-list {
    min-height: 100px;
    max-height: 180px;
    padding: 10px;
  }

  .message-body {
    max-width: 75%;
  }

  .chat-image {
    max-width: 120px;
    max-height: 120px;
  }

  .file-bubble {
    min-width: 140px;
    padding: 6px 10px;
  }

  .input-area {
    padding: 10px;
  }

  /* 工具栏 */
  .toolbar {
    flex-direction: column;
    gap: 10px;
    margin-bottom: 12px;
  }

  .toolbar-left {
    width: 100%;
  }

  .toolbar-left .el-button {
    flex: 1;
  }

  .toolbar-right {
    width: 100%;
  }

  .toolbar-right .el-input {
    width: 100% !important;
  }

  /* 面包屑 */
  .el-breadcrumb {
    margin: 10px 0 !important;
    font-size: 12px;
  }

  /* 表格 */
  .el-table {
    font-size: 13px;
  }

  .el-table :deep(.el-table__cell) {
    padding: 8px 0;
  }

  .el-table :deep(.file-name) {
    font-size: 13px;
  }

  .el-table :deep(.el-button) {
    padding: 4px 8px;
    font-size: 12px;
  }

  /* 分页 */
  .el-pagination {
    flex-wrap: wrap;
    justify-content: center;
  }

  /* 对话框 */
  .el-dialog {
    width: 95% !important;
    margin: 0 auto;
  }
}

@media screen and (max-width: 480px) {
  .space-files {
    padding: 8px;
  }

  .chat-actions .el-button {
    padding: 4px 8px;
  }

  .el-table :deep(.el-table__body-wrapper) {
    overflow-x: auto;
  }
}

/* 邀请好友对话框 */
.invite-friend-list {
  max-height: 400px;
  overflow-y: auto;
}

.invite-friend-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.invite-friend-item:last-child {
  border-bottom: none;
}

.invite-friend-item:hover {
  background-color: #f5f7fa;
}

.friend-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.friend-name {
  font-size: 14px;
}
</style>
