<template>
  <div class="register-container">
    <div class="register-box">
      <div class="register-header">
        <div class="logo-icon">
          <el-icon :size="48"><FolderOpened /></el-icon>
        </div>
        <h2 class="register-title">用户注册</h2>
        <p class="register-subtitle">创建您的账号</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
          />
        </el-form-item>

        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="请输入真实姓名（选填）" />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱（选填）" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleRegister" :loading="loading" style="width: 100%">
            注册
          </el-button>
        </el-form-item>

        <div class="register-footer">
          <span style="color: #909399">已有账号？</span>
          <router-link to="/login" style="color: #409EFF; text-decoration: none">立即登录</router-link>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { FolderOpened } from '@element-plus/icons-vue'
import api from '@/utils/api'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  real_name: '',
  email: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度在 3 到 50 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 100, message: '密码长度在 6 到 100 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const result = await api.post('/auth/register', {
      username: form.username,
      password: form.password,
      real_name: form.real_name || undefined,
      email: form.email || undefined
    })

    userStore.setToken(result.access_token)
    userStore.setUser(result.user)

    ElMessage.success('注册成功')
    router.push('/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 85% 15%, rgba(47, 123, 255, 0.12), transparent 30%),
    radial-gradient(circle at 15% 80%, rgba(124, 92, 255, 0.1), transparent 32%),
    linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
  position: relative;
  overflow: hidden;
}

.register-container::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(47, 123, 255, 0.08) 0%, transparent 40%);
  animation: pulse 15s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    transform: translate(0, 0);
  }
  50% {
    transform: translate(25%, 25%);
  }
}

.register-box {
  width: 440px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 22px;
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
  border: 1px solid rgba(218, 229, 247, 0.92);
  position: relative;
  z-index: 1;
  backdrop-filter: blur(20px);
}

.register-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, #8ae7b9, #28c76f);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 10px 24px rgba(40, 199, 111, 0.28);
}

.register-title {
  font-size: 24px;
  font-weight: 800;
  color: #112544;
  margin: 0 0 8px 0;
}

.register-subtitle {
  font-size: 14px;
  color: #8a97ad;
  margin: 0;
}

.register-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
}

:deep(.el-input__wrapper) {
  padding: 8px 15px;
  border-radius: 12px;
}

:deep(.el-form-item__label) {
  font-weight: 600;
  color: #52627a;
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #55d98d, #24bf69);
  border: none;
  border-radius: 10px;
  font-weight: 600;
  box-shadow: 0 8px 20px rgba(40, 199, 111, 0.22);
  transition: all 0.3s ease;
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #7ae7a8, #55d98d);
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(40, 199, 111, 0.28);
}
</style>
