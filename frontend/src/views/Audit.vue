<template>
  <div class="audit-page">
    <!-- 筛选工具栏 -->
    <el-card style="margin-bottom: 16px">
      <el-form :inline="true">
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 150px">
            <el-option v-for="action in actionTypes" :key="action" :label="action" :value="action" />
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
            <el-tag :type="getActionTagType(row.action)">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_type" label="目标类型" width="100" />
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
        <el-descriptions-item label="操作类型">{{ currentLog?.action }}</el-descriptions-item>
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
import api from '@/utils/api'

const loading = ref(false)
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
    actionTypes.value = res
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

onMounted(() => {
  loadLogs()
  loadActionTypes()
  loadStats()
})
</script>
