<template>
  <div class="profile-page">
    <el-row :gutter="20">
      <!-- 左侧个人信息 -->
      <el-col :span="8">
        <el-card>
          <div class="user-info">
            <el-avatar :size="80" icon="UserFilled" />
            <h3>{{ userStore.user?.real_name || userStore.user?.username }}</h3>
            <el-tag :type="getRoleType(userStore.user?.role?.code)">
              {{ userStore.user?.role?.name || '未分配角色' }}
            </el-tag>
          </div>
          <el-divider />
          <el-descriptions :column="1">
            <el-descriptions-item label="用户名">{{ userStore.user?.username }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ userStore.user?.email || '-' }}</el-descriptions-item>
            <el-descriptions-item label="最后登录">{{ formatDate(userStore.user?.last_login) }}</el-descriptions-item>
            <el-descriptions-item label="注册时间">{{ formatDate(userStore.user?.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 右侧功能区域 -->
      <el-col :span="16">
        <el-tabs v-model="activeTab">
          <!-- 基本信息 -->
          <el-tab-pane label="基本设置" name="profile">
            <el-card>
              <el-form :model="profileForm" label-width="100px" style="max-width: 500px">
                <el-form-item label="姓名">
                  <el-input v-model="profileForm.real_name" />
                </el-form-item>
                <el-form-item label="邮箱">
                  <el-input v-model="profileForm.email" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="updateProfile">保存修改</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-tab-pane>

          <!-- 修改密码 -->
          <el-tab-pane label="修改密码" name="password">
            <el-card>
              <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="100px" style="max-width: 500px">
                <el-form-item label="当前密码" prop="old_password">
                  <el-input v-model="passwordForm.old_password" type="password" show-password />
                </el-form-item>
                <el-form-item label="新密码" prop="new_password">
                  <el-input v-model="passwordForm.new_password" type="password" show-password />
                </el-form-item>
                <el-form-item label="确认密码" prop="confirm_password">
                  <el-input v-model="passwordForm.confirm_password" type="password" show-password />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="changePassword">修改密码</el-button>
                </el-form-item>
              </el-form>
            </el-card>
          </el-tab-pane>

          <!-- 我的上传 -->
          <el-tab-pane label="我的上传" name="uploads">
            <el-card>
              <el-table :data="myFiles" v-loading="filesLoading">
                <el-table-column label="文件名" prop="origin_name" min-width="200" show-overflow-tooltip />
                <el-table-column label="大小" width="100">
                  <template #default="{ row }">{{ formatSize(row.size) }}</template>
                </el-table-column>
                <el-table-column label="上传时间" width="160">
                  <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="120">
                  <template #default="{ row }">
                    <el-button size="small" @click="downloadFile(row)">下载</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <div class="pagination-container">
                <el-pagination
                  v-model:current-page="filesPage"
                  v-model:page-size="filesPageSize"
                  :total="filesTotal"
                  :page-sizes="[10, 20, 50]"
                  layout="total, prev, pager, next"
                  @current-change="loadMyFiles"
                />
              </div>
            </el-card>
          </el-tab-pane>

          <!-- 操作记录 -->
          <el-tab-pane label="操作记录" name="logs">
            <el-card>
              <el-table :data="myLogs" v-loading="logsLoading">
                <el-table-column label="操作" prop="action" width="150">
                  <template #default="{ row }">
                    <el-tag :type="getActionTagType(row.action)" size="small">{{ row.action }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="目标" prop="target_name" min-width="200" show-overflow-tooltip />
                <el-table-column label="结果" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.result ? 'success' : 'danger'" size="small">
                      {{ row.result ? '成功' : '失败' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="时间" width="160">
                  <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                </el-table-column>
              </el-table>
              <div class="pagination-container">
                <el-pagination
                  v-model:current-page="logsPage"
                  v-model:page-size="logsPageSize"
                  :total="logsTotal"
                  :page-sizes="[10, 20, 50]"
                  layout="total, prev, pager, next"
                  @current-change="loadMyLogs"
                />
              </div>
            </el-card>
          </el-tab-pane>

          <!-- 存储统计 -->
          <el-tab-pane label="存储统计" name="storage">
            <el-card>
              <el-row :gutter="20">
                <el-col :span="8">
                  <div class="stat-card">
                    <div class="stat-value">{{ storageStats.file_count }}</div>
                    <div class="stat-label">文件数量</div>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="stat-card">
                    <div class="stat-value">{{ formatSize(storageStats.total_size) }}</div>
                    <div class="stat-label">已用空间</div>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="stat-card">
                    <div class="stat-value">{{ storageStats.folder_count }}</div>
                    <div class="stat-label">文件夹数</div>
                  </div>
                </el-col>
              </el-row>
              <el-divider />
              <h4>文件类型分布</h4>
              <div v-if="storageStats.by_type && storageStats.by_type.length">
                <div v-for="item in storageStats.by_type" :key="item.ext" class="type-item">
                  <span>{{ item.ext || '无扩展名' }}</span>
                  <el-progress :percentage="item.percentage" :stroke-width="10" />
                  <span>{{ item.count }} 个文件</span>
                </div>
              </div>
              <el-empty v-else description="暂无数据" />
            </el-card>
          </el-tab-pane>
        </el-tabs>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'

const userStore = useUserStore()
const activeTab = ref('profile')
const passwordFormRef = ref(null)

const profileForm = reactive({
  real_name: '',
  email: ''
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirm = (rule, value, callback) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

// 我的文件
const myFiles = ref([])
const filesLoading = ref(false)
const filesPage = ref(1)
const filesPageSize = ref(10)
const filesTotal = ref(0)

// 操作记录
const myLogs = ref([])
const logsLoading = ref(false)
const logsPage = ref(1)
const logsPageSize = ref(10)
const logsTotal = ref(0)

// 存储统计
const storageStats = ref({
  file_count: 0,
  folder_count: 0,
  total_size: 0,
  by_type: []
})

const getRoleType = (code) => {
  const typeMap = { 'super_admin': 'danger', 'admin': 'warning', 'user': 'primary', 'guest': 'info' }
  return typeMap[code] || 'info'
}

const getActionTagType = (action) => {
  const typeMap = {
    'login': 'primary', 'logout': 'info', 'file_upload': 'success',
    'file_download': 'warning', 'file_delete': 'danger', 'file_restore': 'success'
  }
  return typeMap[action] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const updateProfile = async () => {
  try {
    await api.put('/users/' + userStore.user.id, profileForm)
    await userStore.fetchCurrentUser()
    ElMessage.success('更新成功')
  } catch (error) {
    ElMessage.error('更新失败')
  }
}

const changePassword = async () => {
  try {
    await passwordFormRef.value.validate()
    await api.put('/auth/password', {
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password
    })
    ElMessage.success('密码修改成功')
    passwordFormRef.value.resetFields()
  } catch (error) {
    if (error !== false) ElMessage.error('修改失败')
  }
}

const loadMyFiles = async () => {
  filesLoading.value = true
  try {
    const res = await api.get('/files', {
      params: { page: filesPage.value, page_size: filesPageSize.value, owner_id: userStore.user.id }
    })
    myFiles.value = res.items || []
    filesTotal.value = res.total || 0
  } catch (error) {
    console.error('加载文件失败:', error)
  } finally {
    filesLoading.value = false
  }
}

const loadMyLogs = async () => {
  logsLoading.value = true
  try {
    const res = await api.get('/audit-logs', {
      params: { page: logsPage.value, page_size: logsPageSize.value, user_id: userStore.user.id }
    })
    myLogs.value = res.items || []
    logsTotal.value = res.total || 0
  } catch (error) {
    console.error('加载日志失败:', error)
  } finally {
    logsLoading.value = false
  }
}

const loadStorageStats = async () => {
  try {
    const res = await api.get('/files/my/stats')
    storageStats.value = res || { file_count: 0, folder_count: 0, total_size: 0, by_type: [] }
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const downloadFile = async (file) => {
  try {
    const response = await fetch(`/api/files/${file.id}/download`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.origin_name
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

onMounted(() => {
  if (userStore.user) {
    profileForm.real_name = userStore.user.real_name || ''
    profileForm.email = userStore.user.email || ''
  }
  loadMyFiles()
  loadMyLogs()
  loadStorageStats()
})
</script>

<style scoped>
.profile-page {
  max-width: 1200px;
}
.user-info {
  text-align: center;
  padding: 20px 0;
}
.user-info h3 {
  margin: 16px 0 8px;
}
.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.stat-card {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #409EFF;
}
.stat-label {
  margin-top: 8px;
  color: #909399;
  font-size: 14px;
}
.type-item {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}
.type-item span:first-child {
  width: 80px;
  text-transform: uppercase;
}
.type-item span:last-child {
  width: 100px;
  text-align: right;
  color: #909399;
  font-size: 13px;
}
</style>
