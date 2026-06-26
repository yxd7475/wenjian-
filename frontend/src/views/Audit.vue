<template>
  <div class="audit-page">
    <!-- 筛选工具栏 -->
    <el-card style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 180px">
            <el-option v-for="action in actionTypes" :key="action.code" :label="action.name" :value="action.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标类型">
          <el-select v-model="filters.targetType" placeholder="全部" clearable style="width: 150px">
            <el-option label="用户" value="user" />
            <el-option label="文件" value="file" />
            <el-option label="文件夹" value="folder" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadLogs">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="success" @click="downloadLogs" :loading="downloading">
            <el-icon style="margin-right: 4px"><Download /></el-icon>
            导出日志
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="6">
        <el-card>
          <div style="text-align: center">
            <div style="font-size: 28px; font-weight: bold; color: #409EFF">{{ stats.total_operations }}</div>
            <div style="color: #909399; margin-top: 8px">操作总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div style="text-align: center">
            <div style="font-size: 28px; font-weight: bold; color: #67C23A">{{ stats.success_count }}</div>
            <div style="color: #909399; margin-top: 8px">成功操作</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div style="text-align: center">
            <div style="font-size: 28px; font-weight: bold; color: #F56C6C">{{ stats.failure_count }}</div>
            <div style="color: #909399; margin-top: 8px">失败操作</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card>
          <div style="text-align: center">
            <div style="font-size: 28px; font-weight: bold; color: #E6A23C">{{ stats.period_days }}</div>
            <div style="color: #909399; margin-top: 8px">统计天数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 日志列表 -->
    <el-card v-loading="loading">
      <el-table :data="logs" style="width: 100%">
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column prop="action" label="操作类型" width="150">
          <template #default="{ row }">
            <el-tag :type="getActionTagType(row.action)">{{ getActionName(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_type" label="目标类型" width="100">
          <template #default="{ row }">
            {{ getTargetTypeName(row.target_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="target_name" label="目标名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag :type="row.result ? 'success' : 'danger'">
              {{ row.result ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP地址" width="140" />
        <el-table-column prop="created_at" label="操作时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetailDialog" title="日志详情" width="600px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用户">{{ currentLog?.username }}</el-descriptions-item>
        <el-descriptions-item label="操作类型">{{ getActionName(currentLog?.action) }}</el-descriptions-item>
        <el-descriptions-item label="目标类型">{{ currentLog?.target_type }}</el-descriptions-item>
        <el-descriptions-item label="目标名称">{{ currentLog?.target_name }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentLog?.ip }}</el-descriptions-item>
        <el-descriptions-item label="结果">
          <el-tag :type="currentLog?.result ? 'success' : 'danger'">
            {{ currentLog?.result ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="操作时间" :span="2">{{ formatDate(currentLog?.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="User-Agent" :span="2">{{ currentLog?.user_agent }}</el-descriptions-item>
        <el-descriptions-item v-if="currentLog?.detail" label="详细信息" :span="2">
          <pre style="margin: 0; white-space: pre-wrap">{{ JSON.stringify(currentLog?.detail, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

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

// 获取操作中文名
const getActionName = (action) => {
  return ACTION_NAMES[action] || action
}

// 目标类型中文翻译
const TARGET_TYPE_NAMES = {
  'user': '用户',
  'file': '文件',
  'folder': '文件夹',
  'system': '系统',
  'share': '分享',
}

// 获取目标类型中文名
const getTargetTypeName = (targetType) => {
  if (!targetType) return '-'
  return TARGET_TYPE_NAMES[targetType] || targetType
}

const loading = ref(false)
const downloading = ref(false)
const logs = ref([])
const actionTypes = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const stats = ref({
  total_operations: 0,
  success_count: 0,
  failure_count: 0,
  period_days: 7
})

const filters = reactive({
  action: '',
  targetType: '',
  dateRange: null
})

const showDetailDialog = ref(false)
const currentLog = ref(null)

// 加载日志列表
const loadLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      action: filters.action || undefined,
      target_type: filters.targetType || undefined,
      start_date: filters.dateRange?.[0],
      end_date: filters.dateRange?.[1]
    }
    const res = await api.get('/audit-logs', { params })
    logs.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('加载日志失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载操作类型
const loadActionTypes = async () => {
  try {
    const res = await api.get('/audit-logs/actions')
    // 如果返回的是对象数组，直接使用；否则转换
    if (res && res.length > 0 && typeof res[0] === 'object') {
      actionTypes.value = res
    } else {
      actionTypes.value = res.map(code => ({ code, name: getActionName(code) }))
    }
  } catch (error) {
    console.error('加载操作类型失败:', error)
  }
}

// 加载统计数据
const loadStats = async () => {
  try {
    const res = await api.get('/audit-logs/stats/summary')
    stats.value = res
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

// 重置筛选
const resetFilters = () => {
  filters.action = ''
  filters.targetType = ''
  filters.dateRange = null
  loadLogs()
}

// 显示详情
const showDetail = (log) => {
  currentLog.value = log
  showDetailDialog.value = true
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 获取操作标签类型
const getActionTagType = (action) => {
  const typeMap = {
    'login': 'primary',
    'logout': 'info',
    'file_upload': 'success',
    'file_download': 'warning',
    'file_delete': 'danger',
    'user_create': 'success',
    'user_update': 'warning',
    'user_delete': 'danger'
  }
  return typeMap[action] || ''
}

// 下载日志
const downloadLogs = async () => {
  downloading.value = true
  try {
    const params = new URLSearchParams()
    if (filters.action) params.append('action', filters.action)
    if (filters.targetType) params.append('target_type', filters.targetType)
    if (filters.dateRange?.[0]) params.append('start_date', filters.dateRange[0])
    if (filters.dateRange?.[1]) params.append('end_date', filters.dateRange[1])

    // 获取token
    const token = localStorage.getItem('token')

    const response = await fetch(`/files/api/audit-logs/export?${params.toString()}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (!response.ok) {
      throw new Error('导出失败')
    }

    // 获取文件名
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = '审计日志.csv'
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=(.+)/)
      if (match) filename = match[1]
    }

    // 下载文件
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    window.URL.revokeObjectURL(url)

    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  loadLogs()
  loadActionTypes()
  loadStats()
})
</script>
