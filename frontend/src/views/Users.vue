<template>
  <div class="users-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建用户
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchUsername"
          placeholder="搜索用户名..."
          prefix-icon="Search"
          clearable
          style="width: 200px"
          @keyup.enter="loadUsers"
          @clear="loadUsers"
        />
        <el-button @click="loadUsers">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 用户列表 -->
    <el-card v-loading="loading">
      <el-table :data="users" style="width: 100%">
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="real_name" label="姓名" width="150" />
        <el-table-column prop="email" label="邮箱" width="200" />
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.is_superuser" type="danger">超级管理员</el-tag>
            <el-tag v-else-if="row.role?.code === 'admin'" type="warning">管理员</el-tag>
            <el-tag v-else-if="row.role?.code === 'user'">普通用户</el-tag>
            <el-tag v-else type="info">访客</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'">
              {{ row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="存储配额" width="200">
          <template #default="{ row }">
            <div class="quota-cell">
              <el-progress
                :percentage="getQuotaPercentage(row)"
                :stroke-width="6"
                :color="getQuotaColor(row)"
                :show-text="false"
                style="flex: 1"
              />
              <span class="quota-text">{{ formatSize(row.storage_used || 0) }} / {{ formatSize(row.storage_quota) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" @click="editUser(row)">编辑</el-button>
              <el-button size="small" @click="editQuota(row)">配额</el-button>
              <el-button size="small" :type="row.status ? 'warning' : 'success'" @click="toggleStatus(row)">{{ row.status ? '禁用' : '启用' }}</el-button>
              <el-button size="small" @click="resetPassword(row)">重置密码</el-button>
              <el-button size="small" type="danger" @click="deleteUser(row)" :disabled="row.is_superuser">删除</el-button>
            </el-button-group>
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
          @size-change="loadUsers"
          @current-change="loadUsers"
        />
      </div>
    </el-card>

    <!-- 创建/编辑用户对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingUser ? '编辑用户' : '新建用户'"
      width="500px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="!!editingUser" />
        </el-form-item>
        <el-form-item v-if="!editingUser" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_id" placeholder="选择角色" style="width: 100%">
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog v-model="showPasswordDialog" title="重置密码" width="400px">
      <el-form @submit.prevent="doResetPassword">
        <el-form-item label="新密码">
          <el-input v-model="newPassword" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPasswordDialog = false">取消</el-button>
        <el-button type="primary" @click="doResetPassword">确定</el-button>
      </template>
    </el-dialog>

    <!-- 修改配额对话框 -->
    <el-dialog v-model="showQuotaDialog" title="修改存储配额" width="450px">
      <div v-if="quotaTarget" style="margin-bottom: 16px">
        <span style="color: var(--text-regular)">用户：</span>
        <strong>{{ quotaTarget.username }}</strong>
        <span style="margin-left: 16px; color: var(--text-light)">
          已使用 {{ formatSize(quotaTarget.storage_used || 0) }}
        </span>
      </div>
      <el-form label-width="80px">
        <el-form-item label="配额大小">
          <el-input-number
            v-model="quotaGB"
            :min="1"
            :max="1000"
            :step="1"
            :precision="0"
            style="width: 200px"
          />
          <span style="margin-left: 8px; color: var(--text-light)">GB</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showQuotaDialog = false">取消</el-button>
        <el-button type="primary" @click="submitQuota">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const loading = ref(false)
const users = ref([])
const roles = ref([])
const departments = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchUsername = ref('')

const showCreateDialog = ref(false)
const showPasswordDialog = ref(false)
const showQuotaDialog = ref(false)
const editingUser = ref(null)
const resetTarget = ref(null)
const newPassword = ref('')
const quotaTarget = ref(null)
const quotaGB = ref(10)

const formRef = ref()
const form = reactive({
  username: '',
  password: '',
  real_name: '',
  email: '',
  role_id: null,
  department_id: null
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value
    }
    if (searchUsername.value) {
      params.username = searchUsername.value
    }
    const res = await api.get('/users', { params })
    users.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('加载用户失败:', error)
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

// 加载角色列表
const loadRoles = async () => {
  try {
    const res = await api.get('/roles')
    roles.value = res.items || res
  } catch (error) {
    console.error('加载角色失败:', error)
  }
}

// 编辑用户
const editUser = (user) => {
  editingUser.value = user
  Object.assign(form, {
    username: user.username,
    real_name: user.real_name,
    email: user.email,
    role_id: user.role_id,
    department_id: user.department_id
  })
  showCreateDialog.value = true
}

// 关闭对话框
const closeDialog = () => {
  showCreateDialog.value = false
  editingUser.value = null
  formRef.value?.resetFields()
  Object.assign(form, {
    username: '',
    password: '',
    real_name: '',
    email: '',
    role_id: null,
    department_id: null
  })
}

// 提交表单
const submitForm = async () => {
  try {
    await formRef.value.validate()
    if (editingUser.value) {
      await api.put(`/users/${editingUser.value.id}`, form)
      ElMessage.success('更新成功')
    } else {
      await api.post('/users', form)
      ElMessage.success('创建成功')
    }
    closeDialog()
    loadUsers()
  } catch (error) {
    console.error('保存用户失败:', error)
  }
}

// 切换状态
const toggleStatus = async (user) => {
  try {
    await api.patch(`/users/${user.id}/status`)
    ElMessage.success('状态已更新')
    loadUsers()
  } catch (error) {
    console.error('更新状态失败:', error)
  }
}

// 重置密码
const resetPassword = (user) => {
  resetTarget.value = user
  newPassword.value = ''
  showPasswordDialog.value = true
}

// 执行重置密码
const doResetPassword = async () => {
  if (!newPassword.value || newPassword.value.length < 6) {
    ElMessage.warning('密码至少6位')
    return
  }
  try {
    await api.post(`/users/${resetTarget.value.id}/reset-password`, {
      user_id: resetTarget.value.id,
      new_password: newPassword.value
    })
    ElMessage.success('密码重置成功')
    showPasswordDialog.value = false
  } catch (error) {
    console.error('重置密码失败:', error)
  }
}

// 删除用户
const deleteUser = async (user) => {
  if (user.is_superuser) {
    ElMessage.warning('不能删除超级管理员')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )
    await api.delete(`/users/${user.id}`)
    ElMessage.success('用户已删除')
    loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除用户失败:', error)
    }
  }
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatSize = (bytes) => {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getQuotaPercentage = (row) => {
  if (!row.storage_quota) return 0
  const used = row.storage_used || 0
  return Math.min(Math.round(used / row.storage_quota * 100), 100)
}

const getQuotaColor = (row) => {
  const pct = getQuotaPercentage(row)
  if (pct >= 90) return '#ff5b6e'
  if (pct >= 70) return '#ff9f43'
  return '#6ba3ff'
}

const editQuota = (user) => {
  quotaTarget.value = user
  quotaGB.value = Math.round((user.storage_quota || 10 * 1024 * 1024 * 1024) / 1024 / 1024 / 1024)
  showQuotaDialog.value = true
}

const submitQuota = async () => {
  if (!quotaTarget.value) return
  try {
    const newQuota = quotaGB.value * 1024 * 1024 * 1024
    await api.put(`/users/${quotaTarget.value.id}`, {
      storage_quota: newQuota
    })
    ElMessage.success(`已将 ${quotaTarget.value.username} 的配额修改为 ${quotaGB.value}GB`)
    showQuotaDialog.value = false
    loadUsers()
  } catch (error) {
    console.error('修改配额失败:', error)
    ElMessage.error('修改配额失败')
  }
}

onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.users-page {
  max-width: 1400px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 22px;
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
  border: 1px solid rgba(218, 229, 247, 0.92);
  backdrop-filter: blur(20px);
}

.toolbar-left, .toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
}

.quota-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quota-text {
  font-size: 11px;
  color: var(--text-light);
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-card) {
  border-radius: 22px;
  border: 1px solid rgba(218, 229, 247, 0.92);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
}

:deep(.el-table) {
  border-radius: 16px;
  overflow: hidden;
}

:deep(.el-table th.el-table__cell) {
  background: rgba(247, 250, 255, 0.9) !important;
  color: #6c7c95;
  font-weight: 700;
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid rgba(229, 237, 250, 0.8);
}

:deep(.el-table__row:hover > td) {
  background: rgba(91, 154, 255, 0.035) !important;
}

:deep(.el-button-group) {
  display: flex;
  flex-wrap: nowrap;
}

:deep(.el-button-group .el-button) {
  margin: 0;
  border-radius: 0;
}

:deep(.el-button-group .el-button:first-child) {
  border-radius: 10px 0 0 10px;
}

:deep(.el-button-group .el-button:last-child) {
  border-radius: 0 10px 10px 0;
}

:deep(.el-dialog) {
  border-radius: 22px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
}

:deep(.el-dialog__title) {
  font-weight: 800;
  color: var(--text-main);
}

:deep(.el-dialog__footer) {
  border-top: 1px solid rgba(224, 233, 248, 0.75);
}
</style>
