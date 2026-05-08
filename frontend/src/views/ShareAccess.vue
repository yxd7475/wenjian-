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

      <!-- 下载区域 -->
      <div v-else style="text-align: center">
        <div style="margin-bottom: 16px">
          <el-button
            v-if="canPreview"
            size="large"
            plain
            @click="showPreviewDialog = true"
          >
            预览文件
          </el-button>
        </div>

        <!-- 下载进度 -->
        <div v-if="downloading" style="margin-bottom: 20px">
          <el-progress
            :percentage="downloadProgress"
            :format="progressFormat"
            :stroke-width="20"
            striped
            striped-flow
          />
          <p style="margin-top: 10px; color: #909399">
            已下载 {{ formatSize(downloadedSize) }} / {{ formatSize(shareInfo.file_size) }}
          </p>
          <p style="color: #909399">{{ downloadSpeed }}</p>
        </div>

        <el-button
          type="primary"
          size="large"
          @click="downloadFile"
          :loading="downloading"
          :disabled="downloading"
        >
          <el-icon style="margin-right: 8px"><Download /></el-icon>
          {{ downloading ? '下载中...' : '下载文件' }}
        </el-button>

        <!-- 大文件提示 -->
        <el-alert
          v-if="shareInfo.file_size > 100 * 1024 * 1024"
          type="info"
          :closable="false"
          style="margin-top: 15px"
        >
          文件较大，请耐心等待下载完成
        </el-alert>
      </div>
    </el-card>

    <FilePreviewDialog
      v-model="showPreviewDialog"
      :file="previewFile"
      :preview-url="previewUrl"
      :text-request="fetchPreviewText"
      @download="downloadFile"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import FilePreviewDialog from '@/components/FilePreviewDialog.vue'
import { getFileExtension, isPreviewable } from '@/utils/file'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const shareInfo = ref(null)
const password = ref('')
const passwordVerified = ref(false)
const downloading = ref(false)
const downloadProgress = ref(0)
const downloadedSize = ref(0)
const downloadSpeed = ref('')
const showPreviewDialog = ref(false)

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

const progressFormat = (percentage) => {
  return percentage === 100 ? '完成' : `${percentage}%`
}

const previewFile = computed(() => {
  if (!shareInfo.value) return null
  return {
    origin_name: shareInfo.value.file_name,
    size: shareInfo.value.file_size,
    ext: shareInfo.value.file_ext || getFileExtension(shareInfo.value.file_name)
  }
})

const canPreview = computed(() => {
  return previewFile.value ? isPreviewable(previewFile.value) : false
})

const previewUrl = computed(() => {
  const shareCode = route.params.code
  if (!shareCode || !previewFile.value) return ''
  const params = new URLSearchParams()
  if (password.value) {
    params.set('password', password.value)
  }
  const query = params.toString()
  return `/api/shares/${shareCode}/preview${query ? `?${query}` : ''}`
})

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

const fetchPreviewText = async () => {
  if (!previewUrl.value) return ''
  const response = await fetch(previewUrl.value)
  if (!response.ok) {
    let message = '读取文件内容失败'
    try {
      const data = await response.json()
      message = data.detail || message
    } catch {
      // ignore json parsing errors
    }
    throw new Error(message)
  }
  return response.text()
}

const downloadFile = async () => {
  const shareCode = route.params.code
  downloading.value = true
  downloadProgress.value = 0
  downloadedSize.value = 0
  downloadSpeed.value = ''

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

    // 获取文件总大小
    const contentLength = response.headers.get('content-length')
    const totalSize = contentLength ? parseInt(contentLength, 10) : shareInfo.value.file_size

    // 读取流并显示进度
    const reader = response.body.getReader()
    const chunks = []
    let receivedLength = 0
    let startTime = Date.now()
    let lastUpdateTime = startTime
    let lastReceivedLength = 0

    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      chunks.push(value)
      receivedLength += value.length
      downloadedSize.value = receivedLength

      // 更新进度
      if (totalSize > 0) {
        downloadProgress.value = Math.round((receivedLength / totalSize) * 100)
      }

      // 计算下载速度（每500ms更新一次）
      const now = Date.now()
      if (now - lastUpdateTime > 500) {
        const timeDiff = (now - lastUpdateTime) / 1000
        const bytesDiff = receivedLength - lastReceivedLength
        const speed = bytesDiff / timeDiff
        downloadSpeed.value = `下载速度: ${formatSize(speed)}/s`
        lastUpdateTime = now
        lastReceivedLength = receivedLength
      }
    }

    // 创建下载
    const blob = new Blob(chunks)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = shareInfo.value.file_name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    // 更新下载次数
    shareInfo.value.download_count++
    downloadProgress.value = 100
    ElMessage.success('下载成功')
  } catch (err) {
    ElMessage.error(err.message || '下载失败')
    downloadProgress.value = 0
  } finally {
    downloading.value = false
    downloadSpeed.value = ''
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
  background:
    radial-gradient(circle at 85% 15%, rgba(47, 123, 255, 0.12), transparent 30%),
    radial-gradient(circle at 15% 80%, rgba(124, 92, 255, 0.1), transparent 32%),
    linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
  padding: 20px;
}
.file-info {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}
.file-details h3 {
  margin: 0 0 8px;
  color: var(--text-main);
}
.file-details p {
  margin: 4px 0;
  color: var(--text-light);
  font-size: 14px;
}

:deep(.el-card) {
  border-radius: 22px;
  border: 1px solid rgba(218, 229, 247, 0.92);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
}
</style>
