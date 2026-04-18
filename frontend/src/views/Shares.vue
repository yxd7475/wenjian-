<template>
  <div class="shares-page">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>我的分享</span>
          <el-button type="primary" @click="loadShares">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <el-alert v-if="!shares.length" type="info" :closable="false" style="margin-bottom: 16px">
        <template #title>
          <span>您还没有创建任何分享</span>
        </template>
        <div style="margin-top: 8px">
          在<a @click="$router.push('/files')" style="color: #409EFF; cursor: pointer">文件管理</a>页面，右键点击文件选择"分享"即可创建分享链接。
        </div>
      </el-alert>

      <el-table :data="shares" v-loading="loading">
        <el-table-column label="文件名" prop="file_name" min-width="150" show-overflow-tooltip />
        <el-table-column label="分享链接" min-width="300">
          <template #default="{ row }">
            <div class="share-link-cell">
              <span class="share-link-text" @click="copyShareLink(row)">{{ getShareLink(row) }}</span>
              <el-button size="small" text type="primary" @click="copyShareLink(row)">
                <el-icon><DocumentCopy /></el-icon> 复制
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="密码" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.password" type="warning" size="small">{{ row.password }}</el-tag>
            <el-tag v-else type="info" size="small">无</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下载次数" width="100">
          <template #default="{ row }">
            {{ row.download_count }} / {{ row.max_downloads || '不限' }}
          </template>
        </el-table-column>
        <el-table-column label="过期时间" width="160">
          <template #default="{ row }">
            <span v-if="row.expire_at">{{ formatDate(row.expire_at) }}</span>
            <span v-else>永不过期</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="getShareStatusType(row)" size="small">
              {{ getShareStatus(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="toggleShare(row)">
              {{ row.is_active ? '关闭' : '开启' }}
            </el-button>
            <el-button size="small" type="danger" @click="deleteShare(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const shares = ref([])
const loading = ref(false)
const serverIp = ref(null)

// 获取服务器 IP
const fetchServerIp = async () => {
  if (serverIp.value) return serverIp.value
  try {
    const data = await api.get('/auth/server-info')
    if (data.local_ips && data.local_ips.length > 0) {
      // 优先选择非 172.x（WSL）的 IP
      const preferredIp = data.local_ips.find(ip => !ip.startsWith('172.'))
      serverIp.value = preferredIp || data.local_ips[0]
    }
    return serverIp.value
  } catch (error) {
    console.error('获取服务器 IP 失败:', error)
    return null
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getShareLink = (share) => {
  let baseUrl = window.location.origin
  if (serverIp.value) {
    baseUrl = `${window.location.protocol}//${serverIp.value}:${window.location.port}`
  }
  return `${baseUrl}/share/${share.share_code}`
}

const getShareStatus = (share) => {
  if (!share.is_active) return '已关闭'
  if (share.expire_at && new Date(share.expire_at) < new Date()) return '已过期'
  if (share.max_downloads > 0 && share.download_count >= share.max_downloads) return '已用完'
  return '有效'
}

const getShareStatusType = (share) => {
  if (!share.is_active) return 'info'
  if (share.expire_at && new Date(share.expire_at) < new Date()) return 'danger'
  if (share.max_downloads > 0 && share.download_count >= share.max_downloads) return 'warning'
  return 'success'
}

const loadShares = async () => {
  loading.value = true
  try {
    shares.value = await api.get('/shares/my')
  } catch (error) {
    console.error('加载分享列表失败:', error)
  } finally {
    loading.value = false
  }
}

const copyShareLink = (share) => {
  const link = getShareLink(share)
  navigator.clipboard.writeText(link)
  ElMessage.success('分享链接已复制: ' + link)
}

const toggleShare = async (share) => {
  try {
    const res = await api.put(`/shares/${share.id}/toggle`)
    ElMessage.success(res.message)
    loadShares()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const deleteShare = async (share) => {
  try {
    await ElMessageBox.confirm('确定要删除此分享吗？', '提示', { type: 'warning' })
    await api.delete(`/shares/${share.id}`)
    ElMessage.success('分享已删除')
    loadShares()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(async () => {
  await fetchServerIp()
  loadShares()
})
</script>

<style scoped>
.shares-page {
  max-width: 1400px;
}
.share-link-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.share-link-text {
  color: #409EFF;
  cursor: pointer;
  word-break: break-all;
  font-size: 13px;
}
.share-link-text:hover {
  text-decoration: underline;
}
</style>
