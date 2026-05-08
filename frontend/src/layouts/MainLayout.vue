<template>
  <div class="main-layout">
    <!-- 手机端遮罩层 -->
    <div v-if="sidebarVisible" class="sidebar-overlay" @click="toggleSidebar"></div>

    <!-- 侧边栏 -->
    <aside :class="['main-aside', { 'sidebar-visible': sidebarVisible, 'main-aside-collapsed': sidebarCollapsed }]">
      <div class="logo">
        <el-icon><FolderOpened /></el-icon>
        <span v-show="!sidebarCollapsed" style="margin-left: 8px">文件共享系统</span>
        <el-button class="close-sidebar" @click="toggleSidebar" circle size="small">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <!-- 空间导航 -->
      <el-menu
        :default-active="activeMenu"
        :collapse="sidebarCollapsed"
        background-color="transparent"
        text-color="#5f6f89"
        active-text-color="#5b9aff"
        router
        @select="handleMenuSelect"
      >
        <!-- 管理员空间 -->
        <el-sub-menu v-if="userStore.isAdmin" index="admin">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>管理员空间</span>
          </template>
          <el-menu-item index="/admin/dashboard">
            <el-icon><DataAnalysis /></el-icon>
            <span>管理后台</span>
          </el-menu-item>
          <el-menu-item index="/admin/users">
            <el-icon><User /></el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/audit">
            <el-icon><Document /></el-icon>
            <span>审计日志</span>
          </el-menu-item>
          <el-menu-item index="/admin/alerts">
            <el-icon><Bell /></el-icon>
            <span>告警中心</span>
          </el-menu-item>
          <el-menu-item index="/admin/backup">
            <el-icon><Box /></el-icon>
            <span>备份恢复</span>
          </el-menu-item>
        </el-sub-menu>

        <!-- 个人空间 -->
        <el-sub-menu index="personal">
          <template #title>
            <el-icon><UserFilled /></el-icon>
            <span>我的空间</span>
          </template>
          <el-menu-item :index="personalSpacePath">
            <el-icon><Files /></el-icon>
            <span>我的文件</span>
          </el-menu-item>
          <el-menu-item index="/shares">
            <el-icon><Share /></el-icon>
            <span>我的分享</span>
          </el-menu-item>
          <el-menu-item index="/profile">
            <el-icon><UserFilled /></el-icon>
            <span>个人中心</span>
          </el-menu-item>
          <el-menu-item index="/friends">
            <el-icon><UserFilled /></el-icon>
            <span>好友管理</span>
            <el-badge v-if="pendingFriendRequests > 0" :value="pendingFriendRequests" class="badge-item" />
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            <span>消息</span>
            <el-badge v-if="chatStore.unreadCount > 0" :value="chatStore.unreadCount" class="badge-item" />
          </el-menu-item>
        </el-sub-menu>

        <!-- 公共空间 -->
        <el-menu-item index="/public">
          <el-icon><Grid /></el-icon>
          <span>公共空间</span>
        </el-menu-item>

        <!-- 群组空间 -->
        <el-sub-menu index="groups">
          <template #title>
            <el-icon><Collection /></el-icon>
            <span>群组空间</span>
          </template>
          <el-menu-item
            v-for="group in groups"
            :key="group.id"
            :index="`/space/${group.space_id}`"
          >
            <el-icon><Folder /></el-icon>
            <span>{{ group.name }}</span>
          </el-menu-item>
          <el-menu-item index="/groups/create">
            <el-icon><Plus /></el-icon>
            <span>创建群组</span>
          </el-menu-item>
          <el-menu-item index="/groups">
            <el-icon><List /></el-icon>
            <span>群组管理</span>
          </el-menu-item>
          <el-menu-item index="/invitations">
            <el-icon><Message /></el-icon>
            <span>邀请消息</span>
            <el-badge v-if="pendingInvitations > 0" :value="pendingInvitations" class="badge-item" />
          </el-menu-item>
        </el-sub-menu>
      </el-menu>

      <!-- 存储空间显示 -->
      <div v-show="!sidebarCollapsed" class="storage-info">
        <div class="storage-header">
          <el-icon :size="16"><Coin /></el-icon>
          <span>存储空间</span>
        </div>
        <el-progress
          :percentage="storagePercentage"
          :stroke-width="8"
          :color="storageColor"
          :show-text="false"
        />
        <div class="storage-text">
          {{ formatStorageSize(storageUsed) }} / {{ formatStorageSize(storageLimit) }}
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-container">
      <header class="main-header">
        <div class="header-left">
          <el-button class="menu-toggle" @click="toggleSidebar" circle size="small">
            <el-icon><Menu /></el-icon>
          </el-button>
          <el-button class="collapse-toggle" @click="toggleCollapse" circle size="small">
            <el-icon><component :is="sidebarCollapsed ? Expand : Fold" /></el-icon>
          </el-button>
          <span class="header-title">{{ currentTitle }}</span>
        </div>
        <div class="header-right">
          <NotificationCenter style="margin-right: 16px" />
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" icon="UserFilled" />
              <span class="user-name">{{ displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'
import { ElMessage } from 'element-plus'
import { Close, Menu, Grid, Expand, Fold, Coin } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { notificationService } from '@/utils/notifications'
import NotificationCenter from '@/components/NotificationCenter.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const chatStore = useChatStore()

const groups = ref([])
const personalSpaceId = ref(null)
const pendingInvitations = ref(0)
const pendingFriendRequests = ref(0)
const sidebarVisible = ref(false)
const sidebarCollapsed = ref(false)
const storageUsed = ref(0)
const storageLimit = ref(10 * 1024 * 1024 * 1024)

const storagePercentage = computed(() => {
  if (storageLimit.value === 0) return 0
  return Math.min(Math.round(storageUsed.value / storageLimit.value * 100), 100)
})

const storageColor = computed(() => {
  if (storagePercentage.value >= 90) return '#ff5b6e'
  if (storagePercentage.value >= 70) return '#ff9f43'
  return '#6ba3ff'
})

const formatStorageSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => route.meta.title || '文件共享系统')
const displayName = computed(() => {
  const user = userStore.user
  return user && user.real_name ? user.real_name : (user && user.username ? user.username : '')
})

const personalSpacePath = computed(() => {
  return personalSpaceId.value ? `/space/${personalSpaceId.value}` : '/files'
})

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  }
}

const toggleSidebar = () => {
  sidebarVisible.value = !sidebarVisible.value
}

const toggleCollapse = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const loadStorageUsage = async () => {
  try {
    const data = await api.get('/spaces/storage/usage')
    storageUsed.value = data.used
    storageLimit.value = data.limit
  } catch (error) {
    console.error('加载存储信息失败:', error)
  }
}

const handleMenuSelect = () => {
  // 手机端点击菜单后关闭侧边栏
  if (window.innerWidth <= 768) {
    sidebarVisible.value = false
  }
}

const loadSpaces = async () => {
  try {
    const spaces = await api.get('/spaces')
    // 找到个人空间
    const personalSpace = spaces.find(s => s.space_type === 'personal')
    if (personalSpace) {
      personalSpaceId.value = personalSpace.id
    }
  } catch (error) {
    console.error('加载空间失败:', error)
  }
}

const loadGroups = async () => {
  try {
    groups.value = await api.get('/groups')
  } catch (error) {
    console.error('加载群组失败:', error)
  }
}

const loadInvitations = async () => {
  try {
    const invitations = await api.get('/invitations')
    pendingInvitations.value = invitations.filter(i => i.status === 'pending').length
  } catch (error) {
    console.error('加载邀请失败:', error)
  }
}

const loadFriendRequests = async () => {
  try {
    const requests = await api.get('/friends/requests')
    pendingFriendRequests.value = requests.length
  } catch (error) {
    console.error('加载好友申请失败:', error)
  }
}

onMounted(() => {
  loadSpaces()
  loadGroups()
  loadInvitations()
  loadFriendRequests()
  loadStorageUsage()
  chatStore.fetchUnreadCount()

  // 连接 WebSocket
  const token = localStorage.getItem('token')
  if (token) {
    notificationService.connect(token)
  }

  // 监听WebSocket消息
  notificationService.on('*', handleWebSocketMessage)
})

// 处理WebSocket消息
const handleWebSocketMessage = (message) => {
  const { type, data } = message

  switch (type) {
    case 'friend_request':
      // 新好友申请
      pendingFriendRequests.value++
      break

    case 'friend_accepted':
      // 好友申请被接受 - 刷新列表
      loadFriendRequests()
      break

    case 'group_invite':
      // 群组邀请
      pendingInvitations.value++
      break

    case 'group_invite_accepted':
      // 邀请被接受，刷新群组列表
      loadGroups()
      loadInvitations()
      break

    case 'group_invite_rejected':
      // 邀请被拒绝，刷新邀请列表
      loadInvitations()
      break

    case 'group_joined':
      // 加入群组成功，刷新群组列表
      loadGroups()
      break

    case 'invitation':
      // 群组邀请（旧类型，兼容）
      pendingInvitations.value++
      break

    case 'invitation_accepted':
      // 邀请被接受，刷新群组列表
      loadGroups()
      loadInvitations()
      break

    case 'chat_message':
      // 聊天消息 - 只有不在聊天页面时才增加未读数
      if (route.path !== '/chat' || route.query.friendId != data.sender_id) {
        chatStore.increaseUnread()
      }
      break

    case 'group_member_joined':
      // 新成员加入群组
      loadGroups()
      break

    case 'group_dissolved':
      // 群组解散
      loadGroups()
      break
  }
}

// 监听路由变化，刷新相关计数
watch(() => route.path, (newPath, oldPath) => {
  // 进入邀请页面时，立即清除红点
  if (newPath === '/invitations') {
    pendingInvitations.value = 0
  }
  // 从邀请页面离开时，刷新邀请计数
  if (oldPath === '/invitations' && newPath !== '/invitations') {
    loadInvitations()
  }

  // 进入好友页面时，立即清除红点
  if (newPath === '/friends') {
    pendingFriendRequests.value = 0
  }
  // 从好友页面离开时，刷新好友申请计数
  if (oldPath === '/friends' && newPath !== '/friends') {
    loadFriendRequests()
  }

  // 进入聊天页面时，立即清除红点
  if (newPath === '/chat') {
    chatStore.unreadCount = 0
    // 稍后从后端刷新真实数据
    setTimeout(() => chatStore.fetchUnreadCount(), 500)
  }
})

// 监听登录状态变化
watch(() => userStore.isLoggedIn, (isLoggedIn) => {
  if (isLoggedIn) {
    const token = localStorage.getItem('token')
    if (token) {
      notificationService.connect(token)
    }
  } else {
    notificationService.disconnect()
  }
})

onUnmounted(() => {
  // 清理WebSocket监听器
  notificationService.off('*', handleWebSocketMessage)
})
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-aside {
  width: 248px;
  min-width: 248px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(18px);
  border-right: 1px solid rgba(220, 230, 246, 0.85);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease, min-width 0.3s ease;
  position: relative;
  overflow: hidden;
}

.main-aside-collapsed {
  width: 64px;
  min-width: 64px;
}

.logo {
  height: 54px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  overflow: hidden;
  white-space: nowrap;
}

.logo .el-icon {
  font-size: 18px;
  color: var(--primary);
  flex-shrink: 0;
}

.logo span {
  font-size: 18px;
  font-weight: 800;
  color: #112544;
}

.close-sidebar {
  display: none;
  margin-left: auto;
  background: transparent;
  border: none;
  color: #5f6f89;
}

.main-aside .el-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
  background: transparent;
}

.main-aside .el-menu:not(.el-menu--collapse) {
  width: 248px;
}

.main-aside .el-menu .el-menu-item {
  color: #5f6f89;
  height: 44px;
  line-height: 44px;
  margin: 4px 8px;
  border-radius: 13px;
  font-size: 14px;
}

.main-aside .el-menu .el-menu-item:hover {
  background: rgba(47, 123, 255, 0.08);
  color: var(--primary);
}

.main-aside .el-menu .el-menu-item.is-active {
  color: var(--primary);
  background: linear-gradient(90deg, rgba(47, 123, 255, 0.16), rgba(47, 123, 255, 0.06));
  font-weight: 700;
  box-shadow: inset 3px 0 0 var(--primary);
}

.main-aside .el-menu .el-sub-menu .el-sub-menu__title {
  color: #5f6f89;
  height: 44px;
  line-height: 44px;
  margin: 4px 8px;
  border-radius: 13px;
  font-size: 14px;
}

.main-aside .el-menu .el-sub-menu .el-sub-menu__title:hover {
  background: rgba(47, 123, 255, 0.08);
  color: var(--primary);
}

.main-aside .el-menu .el-sub-menu.is-active .el-sub-menu__title {
  color: var(--primary);
}

.storage-info {
  padding: 16px 20px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
  background: rgba(247, 250, 255, 0.4);
}

.storage-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-regular);
  margin-bottom: 10px;
}

.storage-text {
  font-size: 11px;
  color: var(--text-light);
  margin-top: 8px;
  text-align: center;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.main-header {
  height: 72px;
  background: rgba(255, 255, 255, 0.68);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(220, 230, 246, 0.72);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 28px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 800;
  color: var(--text-main);
}

.header-title {
  margin-left: 4px;
}

.menu-toggle {
  display: none;
}

.collapse-toggle {
  background: transparent;
  border: none;
  color: var(--text-regular);
  transition: all 0.2s;
}

.collapse-toggle:hover {
  color: var(--primary);
  background: rgba(47, 123, 255, 0.08);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: var(--text-main);
  padding: 8px 14px;
  border-radius: 13px;
  transition: all 0.22s;
}

.user-info:hover {
  background: rgba(47, 123, 255, 0.08);
}

.user-name {
  margin-left: 10px;
  font-size: 14px;
  color: var(--text-regular);
  font-weight: 600;
}

.badge-item {
  margin-left: 8px;
}

.main-content {
  flex: 1;
  overflow: auto;
  background: transparent;
  padding: 26px 28px 40px;
}

.sidebar-overlay {
  display: none;
}

@media screen and (max-width: 768px) {
  .sidebar-overlay {
    display: block;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 99;
  }

  .main-aside {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(-100%);
  }

  .main-aside.sidebar-visible {
    transform: translateX(0);
  }

  .close-sidebar {
    display: flex;
  }

  .menu-toggle {
    display: flex;
  }

  .collapse-toggle {
    display: none;
  }

  .main-header {
    padding: 0 16px;
  }

  .header-title {
    font-size: 16px;
  }

  .user-name {
    display: none;
  }

  .main-content {
    padding: 16px;
  }
}
</style>
