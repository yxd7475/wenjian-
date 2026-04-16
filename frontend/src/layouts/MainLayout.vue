<template>
  <div class="main-layout">
    <!-- 手机端遮罩层 -->
    <div v-if="sidebarVisible" class="sidebar-overlay" @click="toggleSidebar"></div>

    <!-- 侧边栏 -->
    <aside :class="['main-aside', { 'sidebar-visible': sidebarVisible }]">
      <div class="logo">
        <el-icon><FolderOpened /></el-icon>
        <span style="margin-left: 8px">文件共享系统</span>
        <el-button class="close-sidebar" @click="toggleSidebar" circle size="small">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <!-- 空间导航 -->
      <el-menu
        :default-active="activeMenu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
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
    </aside>

    <!-- 主内容区 -->
    <div class="main-container">
      <header class="main-header">
        <div class="header-left">
          <el-button class="menu-toggle" @click="toggleSidebar" circle size="small">
            <el-icon><Menu /></el-icon>
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
import { Close, Menu } from '@element-plus/icons-vue'
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

// 监听路由变化，进入聊天页面时刷新未读数
watch(() => route.path, (newPath) => {
  if (newPath === '/chat') {
    // 进入聊天页面，稍后刷新未读数（等消息标记已读后）
    setTimeout(() => chatStore.fetchUnreadCount(), 500)
  }
})

onMounted(() => {
  loadSpaces()
  loadGroups()
  loadInvitations()
  loadFriendRequests()
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

    case 'invitation':
      // 群组邀请
      pendingInvitations.value++
      break

    case 'invitation_accepted':
      // 邀请被接受，刷新群组列表
      loadGroups()
      loadInvitations()  // 刷新邀请列表
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
  // 从邀请页面离开时，刷新邀请计数
  if (oldPath === '/invitations' && newPath !== '/invitations') {
    loadInvitations()
  }
  // 从好友页面离开时，刷新好友申请计数
  if (oldPath === '/friends' && newPath !== '/friends') {
    loadFriendRequests()
  }
  // 进入聊天页面时，刷新未读数
  if (newPath === '/chat') {
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
  width: 220px;
  min-width: 220px;
  background-color: #304156;
  display: flex;
  flex-direction: column;
  transition: transform 0.3s ease;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  background-color: #263445;
}

.close-sidebar {
  display: none;
  margin-left: auto;
  background: transparent;
  border: none;
  color: #fff;
}

.main-aside .el-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.main-header {
  height: 60px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 500;
}

.header-title {
  margin-left: 12px;
}

.menu-toggle {
  display: none;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #333;
}

.user-name {
  margin-left: 8px;
}

.badge-item {
  margin-left: 8px;
}

.main-content {
  flex: 1;
  overflow: auto;
  background: #f5f7fa;
}

.sidebar-overlay {
  display: none;
}

/* 手机端适配 */
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
    margin-right: 8px;
  }

  .main-header {
    padding: 0 12px;
  }

  .header-title {
    font-size: 15px;
  }

  .user-name {
    display: none;
  }

  .main-content {
    padding: 0;
  }
}
</style>
