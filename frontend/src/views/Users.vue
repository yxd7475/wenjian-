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
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editUser(row)">编辑</el-button>
            <el-button
              size="small"
              :type="row.status ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status ? '禁用' : '启用' }}
            </el-button>
            <el-button size="small" type="danger" @click="resetPassword(row)">
              重置密码
            </el-button>
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
const editingUser = ref(null)
const resetTarget = ref(null)
const newPassword = ref('')

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
      page_size: pageSize.value,
      username: searchUsername.value || undefined
    }
    const res = await api.get('/users', { params })
    users.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('加载用户失败:', error)
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

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>
