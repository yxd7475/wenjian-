import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/s/:code',
    name: 'ShareAccess',
    component: () => import('@/views/ShareAccess.vue'),
    meta: { requiresAuth: false }
  },
  // 兼容旧链接
  {
    path: '/share/:code',
    redirect: to => ({ path: `/s/${to.params.code}` })
  },
  {
    path: '/join/:code',
    name: 'JoinGroup',
    component: () => import('@/views/JoinGroup.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/files'
      },
      {
        path: 'files',
        name: 'Files',
        component: () => import('@/views/Files.vue'),
        meta: { title: '文件管理' }
      },
      // 公共空间路由
      {
        path: 'public',
        name: 'PublicSpace',
        component: () => import('@/views/PublicSpace.vue'),
        meta: { title: '公共空间' }
      },
      // 空间路由
      {
        path: 'space/:id',
        name: 'SpaceFiles',
        component: () => import('@/views/SpaceFiles.vue'),
        meta: { title: '空间文件' }
      },
      // 管理员空间路由
      {
        path: 'admin/dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '管理后台', requiresAdmin: true }
      },
      {
        path: 'admin/users',
        name: 'AdminUsers',
        component: () => import('@/views/Users.vue'),
        meta: { title: '用户管理', requiresAdmin: true }
      },
      {
        path: 'admin/audit',
        name: 'AdminAudit',
        component: () => import('@/views/Audit.vue'),
        meta: { title: '审计日志', requiresAdmin: true }
      },
      {
        path: 'admin/alerts',
        name: 'AdminAlerts',
        component: () => import('@/views/Alerts.vue'),
        meta: { title: '告警中心', requiresAdmin: true }
      },
      {
        path: 'admin/backup',
        name: 'AdminBackup',
        component: () => import('@/views/Backup.vue'),
        meta: { title: '备份恢复', requiresAdmin: true }
      },
      // 兼容旧路由
      {
        path: 'users',
        redirect: '/admin/users'
      },
      {
        path: 'audit',
        redirect: '/admin/audit'
      },
      {
        path: 'alerts',
        redirect: '/admin/alerts'
      },
      {
        path: 'backup',
        redirect: '/admin/backup'
      },
      {
        path: 'dashboard',
        redirect: '/admin/dashboard'
      },
      // 群组路由
      {
        path: 'groups',
        name: 'Groups',
        component: () => import('@/views/Groups.vue'),
        meta: { title: '群组管理' }
      },
      {
        path: 'groups/create',
        name: 'GroupCreate',
        component: () => import('@/views/GroupDetail.vue'),
        meta: { title: '创建群组' }
      },
      {
        path: 'groups/:id',
        name: 'GroupDetail',
        component: () => import('@/views/GroupDetail.vue'),
        meta: { title: '群组详情' }
      },
      {
        path: 'invitations',
        name: 'Invitations',
        component: () => import('@/views/Invitations.vue'),
        meta: { title: '邀请消息' }
      },
      // 其他路由
      {
        path: 'shares',
        name: 'Shares',
        component: () => import('@/views/Shares.vue'),
        meta: { title: '我的分享' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置' }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'friends',
        name: 'Friends',
        component: () => import('@/views/Friends.vue'),
        meta: { title: '好友管理' }
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/Chat.vue'),
        meta: { title: '消息' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next('/files')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    next('/files')
  } else {
    next()
  }
})

export default router
