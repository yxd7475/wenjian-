<template>
  <div class="login-container">
    <div class="login-box">
      <div class="login-header">
        <div class="logo-icon">
          <el-icon :size="48"><FolderOpened /></el-icon>
        </div>
        <h2 class="login-title">局域网文件共享系统</h2>
        <p class="login-subtitle">安全 · 高效 · 便捷</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            native-type="submit"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footer">
        <span style="color: #909399">还没有账号？</span>
        <router-link to="/register" style="color: #409EFF; text-decoration: none">立即注册</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { FolderOpened } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  try {
    await formRef.value.validate()
    loading.value = true
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/files')
  } catch (error) {
    console.error('登录失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
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

.login-container::before {
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

.login-box {
  width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 22px;
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
  border: 1px solid rgba(218, 229, 247, 0.92);
  position: relative;
  z-index: 1;
  backdrop-filter: blur(20px);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-icon {
  width: 72px;
  height: 72px;
  margin: 0 auto 16px;
  background: linear-gradient(135deg, #6ba3ff, #5b9aff);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 8px 20px rgba(91, 154, 255, 0.28);
}

.login-title {
  font-size: 24px;
  font-weight: 800;
  color: #112544;
  margin: 0 0 8px 0;
}

.login-subtitle {
  font-size: 14px;
  color: #8a97ad;
  margin: 0;
}

.login-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
}

:deep(.el-input__wrapper) {
  padding: 8px 15px;
  border-radius: 12px;
}

:deep(.el-button--primary) {
  background: linear-gradient(135deg, #6ba3ff, #5b9aff);
  border: none;
  border-radius: 10px;
  font-weight: 600;
  color: #fff !important;
  box-shadow: 0 8px 20px rgba(91, 154, 255, 0.25);
  transition: all 0.3s ease;
}

:deep(.el-button--primary:hover) {
  background: linear-gradient(135deg, #85b5ff, #6ba3ff);
  color: #fff !important;
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(91, 154, 255, 0.32);
}
</style>
