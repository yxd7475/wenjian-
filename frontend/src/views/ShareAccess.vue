<template>
  <div class="share-access-page">
    <el-card v-if="loading" style="text-align: center; padding: 40px">
      <el-icon class="is-loading" :size="40"><Loading /></el-icon>
      <p>加载中...</p>
    </el-card>

    <el-card v-else-if="error" style="text-align: center; padding: 40px">
      <el-icon :size="60" color="#F56C6C"><WarningFilled /></el-icon>
      <h2>{{ error }}</h2>
      <el-button type="primary" @click="$router.push('/login')">返回登录</el-button>
    </el-card>

    <el-card v-else style="max-width: 600px; margin: 0 auto">
      <template #header>
        <div style="display: flex; align-items: center">
          <el-icon :size="24" style="margin-right: 8px"><Link /></el-icon>
          <span>文件分享</span>
        </div>
      </template>

      <div class="file-info">
        <el-icon :size="48" color="#409EFF"><Document /></el-icon>
        <div class="file-details">
          <h3>{{ shareInfo.file_name }}</h3>
          <p>文件大小：{{ formatSize(shareInfo.file_size) }}</p>
          <p v-if="shareInfo.expire_at">过期时间：{{ formatDate(shareInfo.expire_at) }}</p>
          <p>下载次数：{{ shareInfo.download_count }} / {{ shareInfo.max_downloads || '不限' }}</p>
        </div>
      </div>

      <el-divider />

      <!-- 密码输入 -->
      <el-form v-if="shareInfo.has_password && !passwordVerified" @submit.prevent="verifyPassword">
        <el-form-item label="访问密码">
          <el-input v-model="password" type="password" placeholder="请输入访问密码" show-password />
        </el-form-item>
        <el-button type="primary" @click="verifyPassword" style="width: 100%">验证密码</el-button>
      </el-form>

      <!-- 下载按钮 -->
      <div v-else style="text-align: center">
        <el-button type="primary" size="large" @click="downloadFile" :loading="downloading">
          <el-icon style="margin-right: 8px"><Download /></el-icon>
          下载文件
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const shareInfo = ref(null)
const password = ref('')
const passwordVerified = ref(false)
const downloading = ref(false)

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

const loadShareInfo = async () => {
  const shareCode = route.params.code
  if (!shareCode) {
    error.value = '无效的分享链接'
    loading.value = false
    return
  }

  try {
    shareInfo.value = await api.get(`/shares/${shareCode}`)
    // 如果没有密码，直接可以下载
    if (!shareInfo.value.has_password) {
      passwordVerified.value = true
    }
  } catch (err) {
    const detail = err.response?.data?.detail
    error.value = detail || '分享不存在或已失效'
  } finally {
    loading.value = false
  }
}

const verifyPassword = async () => {
  if (!password.value) {
    ElMessage.warning('请输入密码')
    return
  }

  const shareCode = route.params.code

  try {
    // 调用后端验证密码
    await api.post(`/shares/${shareCode}/verify`, { password: password.value })
    passwordVerified.value = true
    ElMessage.success('密码验证成功')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '密码错误')
    passwordVerified.value = false
  }
}

const downloadFile = async () => {
  const shareCode = route.params.code
  downloading.value = true

  try {
    const response = await fetch(`/api/shares/${shareCode}/download`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ password: password.value || null })
    })

    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || '下载失败')
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = shareInfo.value.file_name
    link.click()
    window.URL.revokeObjectURL(url)

    // 更新下载次数
    shareInfo.value.download_count++
    ElMessage.success('下载成功')
  } catch (err) {
    ElMessage.error(err.message || '下载失败')
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  loadShareInfo()
})
</script>

<style scoped>
.share-access-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  padding: 20px;
}
.file-info {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}
.file-details h3 {
  margin: 0 0 8px;
  color: #303133;
}
.file-details p {
  margin: 4px 0;
  color: #909399;
  font-size: 14px;
}
</style>
