<template>
  <div class="backup-page">
    <!-- 定时备份配置 -->
    <el-card style="margin-bottom: 20px">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>定时备份</span>
          <el-switch v-model="scheduleConfig.enabled" @change="saveSchedule" />
        </div>
      </template>
      <el-form :disabled="!scheduleConfig.enabled" inline>
        <el-form-item label="备份时间">
          <el-time-select
            v-model="scheduleTime"
            start="00:00"
            step="01:00"
            end="23:00"
            placeholder="选择时间"
            style="width: 120px"
            @change="saveSchedule"
          />
        </el-form-item>
        <el-form-item>
          <span style="color: #909399; font-size: 13px">
            每天凌晨 {{ scheduleTime }} 自动执行完整备份
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 备份操作 -->
    <el-card style="margin-bottom: 20px">
      <template #header>
        <span>手动备份</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card shadow="hover" class="backup-option" @click="createBackup('full')">
            <div class="backup-icon" style="background: #409EFF">
              <el-icon :size="32"><Files /></el-icon>
            </div>
            <div class="backup-info">
              <div class="backup-title">完整备份</div>
              <div class="backup-desc">备份数据库和所有文件</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="backup-option" @click="createBackup('data')">
            <div class="backup-icon" style="background: #67C23A">
              <el-icon :size="32"><Coin /></el-icon>
            </div>
            <div class="backup-info">
              <div class="backup-title">数据库备份</div>
              <div class="backup-desc">仅备份数据库文件</div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="backup-option" @click="createBackup('files')">
            <div class="backup-icon" style="background: #E6A23C">
              <el-icon :size="32"><Folder /></el-icon>
            </div>
            <div class="backup-info">
              <div class="backup-title">文件备份</div>
              <div class="backup-desc">仅备份上传的文件</div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 备份列表 -->
    <el-card>
      <template #header>
        <span>备份记录</span>
      </template>
      <el-table :data="backups" v-loading="loading">
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getBackupTypeStyle(row.backup_type)" size="small">
              {{ getBackupTypeName(row.backup_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文件大小" width="120">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" prop="message" show-overflow-tooltip />
        <el-table-column label="创建时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="restoreBackup(row)" :disabled="row.status !== 1">
              恢复
            </el-button>
            <el-button size="small" @click="downloadBackup(row)" :disabled="row.status !== 1">
              下载
            </el-button>
            <el-button size="small" type="danger" @click="deleteBackup(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 恢复确认对话框 -->
    <el-dialog v-model="showRestoreDialog" title="恢复确认" width="500px">
      <el-alert type="warning" title="警告" :closable="false" style="margin-bottom: 16px">
        恢复备份将覆盖当前数据，此操作不可逆！建议先创建新的备份。
      </el-alert>
      <p>确定要恢复此备份吗？</p>
      <p><strong>备份类型：</strong>{{ getBackupTypeName(restoreTarget?.backup_type) }}</p>
      <p><strong>创建时间：</strong>{{ formatDate(restoreTarget?.created_at) }}</p>
      <template #footer>
        <el-button @click="showRestoreDialog = false">取消</el-button>
        <el-button type="danger" @click="confirmRestore" :loading="restoring">确认恢复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const backups = ref([])
const loading = ref(false)
const showRestoreDialog = ref(false)
const restoreTarget = ref(null)
const restoring = ref(false)

// 定时备份配置
const scheduleConfig = ref({ enabled: true, hour: 2, minute: 0 })
const scheduleTime = computed({
  get: () => `${String(scheduleConfig.value.hour).padStart(2, '0')}:00`,
  set: (val) => {
    scheduleConfig.value.hour = parseInt(val.split(':')[0])
    scheduleConfig.value.minute = 0
  }
})

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

const getBackupTypeName = (type) => {
  const map = { 'full': '完整备份', 'data': '数据库', 'files': '文件' }
  return map[type] || type
}

const getBackupTypeStyle = (type) => {
  const map = { 'full': 'primary', 'data': 'success', 'files': 'warning' }
  return map[type] || 'info'
}

const getStatusName = (status) => {
  const map = { 0: '进行中', 1: '成功', 2: '失败' }
  return map[status] || '未知'
}

const getStatusType = (status) => {
  const map = { 0: 'warning', 1: 'success', 2: 'danger' }
  return map[status] || 'info'
}

const loadBackups = async () => {
  loading.value = true
  try {
    backups.value = await api.get('/backup')
  } catch (error) {
    console.error('加载备份列表失败:', error)
  } finally {
    loading.value = false
  }
}

const createBackup = async (type) => {
  try {
    await ElMessageBox.confirm(
      `确定要创建${getBackupTypeName(type)}吗？`,
      '创建备份',
      { type: 'info' }
    )
    await api.post('/backup', { backup_type: type, include_files: true })
    ElMessage.success('备份任务已开始，请稍后刷新查看')
    loadBackups()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('创建备份失败')
  }
}

const restoreBackup = (backup) => {
  restoreTarget.value = backup
  showRestoreDialog.value = true
}

const confirmRestore = async () => {
  restoring.value = true
  try {
    const res = await api.post(`/backup/${restoreTarget.value.id}/restore`)
    ElMessage.success(res.message)
    showRestoreDialog.value = false
  } catch (error) {
    ElMessage.error('恢复失败')
  } finally {
    restoring.value = false
  }
}

const downloadBackup = async (backup) => {
  const token = localStorage.getItem('token')
  window.open(`/api/backup/download/${backup.id}?token=${token}`, '_blank')
}

const deleteBackup = async (backup) => {
  try {
    await ElMessageBox.confirm('确定要删除此备份吗？', '提示', { type: 'warning' })
    await api.delete(`/backup/${backup.id}`)
    ElMessage.success('备份已删除')
    loadBackups()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => {
  loadBackups()
  loadSchedule()
})

// 加载定时备份配置
const loadSchedule = async () => {
  try {
    const res = await api.get('/backup/schedule')
    scheduleConfig.value = res
  } catch (error) {
    console.error('加载定时备份配置失败:', error)
  }
}

// 保存定时备份配置
const saveSchedule = async () => {
  try {
    await api.post('/backup/schedule', {
      enabled: scheduleConfig.value.enabled,
      hour: scheduleConfig.value.hour,
      minute: scheduleConfig.value.minute
    })
    ElMessage.success('定时备份配置已保存')
  } catch (error) {
    ElMessage.error('保存配置失败')
  }
}
</script>

<style scoped>
.backup-page {
  max-width: 1200px;
}
.backup-option {
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 20px;
  transition: transform 0.2s;
}
.backup-option:hover {
  transform: translateY(-4px);
}
.backup-option :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 20px;
}
.backup-icon {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-right: 16px;
}
.backup-info {
  flex: 1;
}
.backup-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}
.backup-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
</style>
