<template>
  <div class="alerts-page">
    <!-- 统计卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value danger">{{ stats.danger }}</div>
          <div class="stat-label">严重告警</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value warning">{{ stats.warning }}</div>
          <div class="stat-label">警告</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value info">{{ stats.info }}</div>
          <div class="stat-label">信息</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.unread }}</div>
          <div class="stat-label">未读</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选和操作 -->
    <el-card style="margin-bottom: 20px">
      <el-row :gutter="20" align="middle">
        <el-col :span="6">
          <el-select v-model="filterSeverity" placeholder="选择级别" clearable @change="loadAlerts">
            <el-option label="严重" value="danger" />
            <el-option label="警告" value="warning" />
            <el-option label="信息" value="info" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-checkbox v-model="showUnread" @change="loadAlerts">仅显示未读</el-checkbox>
        </el-col>
        <el-col :span="12" style="text-align: right">
          <el-button @click="markAllRead" :disabled="stats.unread === 0">全部标记已读</el-button>
          <el-button type="primary" @click="loadAlerts">刷新</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 告警列表 -->
    <el-card>
      <el-table :data="alerts" v-loading="loading">
        <el-table-column label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="row.severity" size="small">
              {{ getSeverityName(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            {{ getAlertTypeName(row.alert_type) }}
          </template>
        </el-table-column>
        <el-table-column label="标题" prop="title" min-width="200" />
        <el-table-column label="内容" prop="content" min-width="300" show-overflow-tooltip />
        <el-table-column label="相关用户" prop="username" width="100" />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_handled" type="success" size="small">已处理</el-tag>
            <el-tag v-else-if="row.is_read" type="info" size="small">已读</el-tag>
            <el-tag v-else type="warning" size="small">未读</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="!row.is_read" size="small" @click="markRead(row)">标记已读</el-button>
            <el-button v-if="!row.is_handled" size="small" type="primary" @click="handleAlert(row)">处理</el-button>
            <el-button size="small" type="danger" @click="deleteAlert(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const alerts = ref([])
const stats = ref({ total: 0, unread: 0, danger: 0, warning: 0, info: 0 })
const loading = ref(false)
const filterSeverity = ref('')
const showUnread = ref(false)

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getSeverityName = (severity) => {
  const map = { 'danger': '严重', 'warning': '警告', 'info': '信息' }
  return map[severity] || severity
}

const getAlertTypeName = (type) => {
  const map = {
    'sensitive_download': '敏感文件下载',
    'batch_delete': '批量删除',
    'login_failed': '登录失败',
    'high_privilege': '高权限操作'
  }
  return map[type] || type
}

const loadAlerts = async () => {
  loading.value = true
  try {
    const params = {}
    if (filterSeverity.value) params.severity = filterSeverity.value
    if (showUnread.value) params.is_read = false

    alerts.value = await api.get('/alerts', { params })
  } catch (error) {
    console.error('加载告警失败:', error)
  } finally {
    loading.value = false
  }
}

const loadStats = async () => {
  try {
    stats.value = await api.get('/alerts/stats')
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const markRead = async (alert) => {
  try {
    await api.put(`/alerts/${alert.id}/read`)
    alert.is_read = true
    loadStats()
    ElMessage.success('已标记为已读')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleAlert = async (alert) => {
  try {
    await api.put(`/alerts/${alert.id}/handle`)
    alert.is_read = true
    alert.is_handled = true
    loadStats()
    ElMessage.success('已标记为已处理')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const markAllRead = async () => {
  try {
    await api.put('/alerts/read-all')
    loadAlerts()
    loadStats()
    ElMessage.success('已全部标记为已读')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const deleteAlert = async (alert) => {
  try {
    await ElMessageBox.confirm('确定要删除此告警吗？', '提示', { type: 'warning' })
    await api.delete(`/alerts/${alert.id}`)
    loadAlerts()
    loadStats()
    ElMessage.success('告警已删除')
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadAlerts()
  loadStats()
})
</script>

<style scoped>
.alerts-page {
  max-width: 1400px;
}
.stat-card {
  text-align: center;
  padding: 20px;
}
.stat-card :deep(.el-card__body) {
  padding: 20px;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
}
.stat-value.danger {
  color: #F56C6C;
}
.stat-value.warning {
  color: #E6A23C;
}
.stat-value.info {
  color: #409EFF;
}
.stat-label {
  color: #909399;
  margin-top: 8px;
}
</style>
