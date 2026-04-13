<template>
  <div class="dashboard-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: #409EFF">
            <el-icon :size="32"><User /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.user_count }}</div>
            <div class="stat-label">用户总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: #67C23A">
            <el-icon :size="32"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.file_count }}</div>
            <div class="stat-label">文件总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: #E6A23C">
            <el-icon :size="32"><Folder /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.folder_count }}</div>
            <div class="stat-label">文件夹数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-icon" style="background: #F56C6C">
            <el-icon :size="32"><Coin /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ formatSize(stats.storage_used) }}</div>
            <div class="stat-label">存储已用</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <!-- 最近操作日志 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>最近操作</span>
              <el-button text type="primary" @click="$router.push('/audit')">查看全部</el-button>
            </div>
          </template>
          <el-table :data="recentLogs" v-loading="logsLoading" size="small">
            <el-table-column label="用户" prop="username" width="100" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-tag :type="getActionTagType(row.action)" size="small">{{ getActionName(row.action) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="目标" prop="target_name" show-overflow-tooltip />
            <el-table-column label="时间" width="140">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 大文件排行 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>大文件排行</span>
          </template>
          <el-table :data="largeFiles" v-loading="filesLoading" size="small">
            <el-table-column label="文件名" prop="origin_name" show-overflow-tooltip />
            <el-table-column label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="上传者" width="100">
              <template #default="{ row }">{{ row.owner?.username || '-' }}</template>
            </el-table-column>
            <el-table-column label="时间" width="140">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <!-- 文件类型分布 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>文件类型分布</span>
          </template>
          <div v-if="fileTypeStats.length">
            <div v-for="item in fileTypeStats" :key="item.ext" class="type-row">
              <div class="type-name">{{ item.ext || '其他' }}</div>
              <el-progress :percentage="item.percentage" :stroke-width="16" :show-text="false" style="flex: 1" />
              <div class="type-count">{{ item.count }} ({{ formatSize(item.size) }})</div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>

      <!-- 用户活跃度 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>用户活跃度</span>
          </template>
          <el-table :data="activeUsers" size="small">
            <el-table-column label="用户" prop="username" width="120" />
            <el-table-column label="操作次数" prop="count" width="100" />
            <el-table-column label="最后活跃" width="160">
              <template #default="{ row }">{{ formatDate(row.last_active) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 高风险操作 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span style="color: #F56C6C">高风险操作记录</span>
      </template>
      <el-table :data="riskOperations" v-loading="riskLoading" size="small">
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="用户" prop="username" width="100" />
        <el-table-column label="操作类型" prop="action" width="150">
          <template #default="{ row }">
            <el-tag type="danger" size="small">{{ getActionName(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标" prop="target_name" show-overflow-tooltip />
        <el-table-column label="IP地址" prop="ip" width="140" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.result ? 'success' : 'danger'" size="small">
              {{ row.result ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'

const stats = ref({
  user_count: 0,
  file_count: 0,
  folder_count: 0,
  storage_used: 0
})

const recentLogs = ref([])
const largeFiles = ref([])
const fileTypeStats = ref([])
const activeUsers = ref([])
const riskOperations = ref([])

const logsLoading = ref(false)
const filesLoading = ref(false)
const riskLoading = ref(false)

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getActionTagType = (action) => {
  const typeMap = {
    'login': 'primary', 'logout': 'info', 'file_upload': 'success',
    'file_download': 'warning', 'file_delete': 'danger'
  }
  return typeMap[action] || ''
}

// 操作类型中文翻译
const ACTION_NAMES = {
  'login': '登录',
  'logout': '登出',
  'password_change': '修改密码',
  'password_reset': '重置密码',
  'folder_create': '创建文件夹',
  'folder_delete': '删除文件夹',
  'folder_rename': '重命名文件夹',
  'file_upload': '上传文件',
  'file_download': '下载文件',
  'file_delete': '删除文件',
  'file_batch_delete': '批量删除文件',
  'file_rename': '重命名文件',
  'file_move': '移动文件',
  'file_copy': '复制文件',
  'file_restore': '恢复文件',
  'file_permanent_delete': '永久删除文件',
  'trash_empty': '清空回收站',
  'file_share': '分享文件',
  'share_enable': '启用分享',
  'share_disable': '禁用分享',
  'share_delete': '删除分享',
  'user_create': '创建用户',
  'user_delete': '删除用户',
  'user_update': '更新用户',
  'user_status_toggle': '切换用户状态',
  'version_rollback': '版本回滚',
  'version_delete': '删除版本',
  'backup_create': '创建备份',
  'backup_restore': '恢复备份',
  'backup_delete': '删除备份',
}

const getActionName = (action) => {
  return ACTION_NAMES[action] || action
}

const loadStats = async () => {
  try {
    const res = await api.get('/dashboard/stats')
    stats.value = res || stats.value
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const loadRecentLogs = async () => {
  logsLoading.value = true
  try {
    const res = await api.get('/audit-logs', { params: { page_size: 10 } })
    recentLogs.value = res.items || []
  } catch (error) {
    console.error('加载日志失败:', error)
  } finally {
    logsLoading.value = false
  }
}

const loadLargeFiles = async () => {
  filesLoading.value = true
  try {
    const res = await api.get('/dashboard/large-files')
    largeFiles.value = res || []
  } catch (error) {
    console.error('加载大文件失败:', error)
  } finally {
    filesLoading.value = false
  }
}

const loadFileTypeStats = async () => {
  try {
    const res = await api.get('/dashboard/file-types')
    fileTypeStats.value = res || []
  } catch (error) {
    console.error('加载文件类型统计失败:', error)
  }
}

const loadActiveUsers = async () => {
  try {
    const res = await api.get('/dashboard/active-users')
    activeUsers.value = res || []
  } catch (error) {
    console.error('加载活跃用户失败:', error)
  }
}

const loadRiskOperations = async () => {
  riskLoading.value = true
  try {
    const res = await api.get('/dashboard/risk-operations')
    riskOperations.value = res || []
  } catch (error) {
    console.error('加载风险操作失败:', error)
  } finally {
    riskLoading.value = false
  }
}

onMounted(() => {
  loadStats()
  loadRecentLogs()
  loadLargeFiles()
  loadFileTypeStats()
  loadActiveUsers()
  loadRiskOperations()
})
</script>

<style scoped>
.dashboard-page {
  max-width: 1400px;
}
.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
}
.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
}
.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-right: 16px;
}
.stat-info {
  flex: 1;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}
.stat-label {
  color: #909399;
  font-size: 14px;
  margin-top: 4px;
}
.type-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}
.type-name {
  width: 60px;
  text-transform: uppercase;
  font-size: 13px;
  color: #606266;
}
.type-count {
  width: 120px;
  text-align: right;
  font-size: 13px;
  color: #909399;
}
</style>
