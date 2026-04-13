<template>
  <div class="settings-page">
    <el-card>
      <template #header>
        <span>个人设置</span>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="profile">
          <el-form :model="profileForm" label-width="100px" style="max-width: 500px">
            <el-form-item label="用户名">
              <el-input v-model="userStore.user.username" disabled />
            </el-form-item>
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
        </el-tab-pane>

        <el-tab-pane label="修改密码" name="password">
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
        </el-tab-pane>

        <el-tab-pane label="关于" name="about">
          <el-descriptions :column="1" border style="max-width: 500px">
            <el-descriptions-item label="系统名称">局域网文件共享系统</el-descriptions-item>
            <el-descriptions-item label="版本">1.0.0</el-descriptions-item>
            <el-descriptions-item label="技术栈">Vue 3 + Element Plus + FastAPI</el-descriptions-item>
            <el-descriptions-item label="功能特性">文件上传/下载、文件夹管理、权限控制、审计日志</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
      </el-tabs>
    </el-card>
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

onMounted(() => {
  if (userStore.user) {
    profileForm.real_name = userStore.user.real_name || ''
    profileForm.email = userStore.user.email || ''
  }
})

const updateProfile = async () => {
  try {
    await api.put('/users/' + userStore.user.id, profileForm)
    await userStore.fetchCurrentUser()
    ElMessage.success('更新成功')
  } catch (error) {
    console.error('更新失败:', error)
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
    console.error('修改密码失败:', error)
  }
}
</script>

<style scoped>
.settings-page {
  max-width: 800px;
}
</style>
