<template>
  <div class="public-space">
    <el-page-header title="返回" @back="goBack">
      <template #content>
        <span class="page-title">公共空间</span>
      </template>
      <template #extra>
        <el-tag type="success" size="small">所有用户可见</el-tag>
      </template>
    </el-page-header>

    <el-divider />

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon> 上传文件
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索公共文件（支持模糊搜索）"
          style="width: 280px"
          clearable
          @keyup.enter="searchFiles"
          @clear="clearSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="searchFiles" style="margin-left: 8px">
          <el-icon><Search /></el-icon> 搜索
        </el-button>
      </div>
    </div>

    <!-- 分类标签 -->
    <div class="category-tabs">
      <el-radio-group v-model="selectedCategory" @change="handleCategoryChange">
        <el-radio-button :value="null">全部</el-radio-button>
        <el-radio-button
          v-for="cat in categories"
          :key="cat.id"
          :value="cat.id"
        >
          <el-icon v-if="cat.icon"><component :is="cat.icon" /></el-icon>
          {{ cat.name }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 文件列表 -->
    <el-table :data="files" v-loading="loading" @row-click="handleRowClick">
      <el-table-column label="名称" min-width="300">
        <template #default="{ row }">
          <div class="file-name">
            <div class="file-icon-wrapper" :style="{ background: resolveFileIconBg(row) }">
              <el-icon :size="18" color="#fff">
                <component :is="resolveFileIcon(row)" />
              </el-icon>
            </div>
            <span style="margin-left: 8px">{{ row.origin_name }}</span>
            <el-tag v-if="row.category" size="small" :color="row.category.color" style="margin-left: 8px" effect="dark">
              {{ row.category.name }}
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="120">
        <template #default="{ row }">
          {{ formatSize(row.size) }}
        </template>
      </el-table-column>
      <el-table-column label="上传者" width="120">
        <template #default="{ row }">
          {{ row.owner?.real_name || row.owner?.username || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="上传时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" type="primary" plain @click.stop="previewFileItem(row)" v-if="canPreview(row)">预览</el-button>
            <el-button size="small" @click.stop="downloadFile(row)">下载</el-button>
            <el-button size="small" type="primary" @click.stop="openShareDialog(row)">分享</el-button>
            <el-button size="small" type="danger" @click.stop="deleteFile(row)" v-if="canDelete(row)">删除</el-button>
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @size-change="loadFiles"
      @current-change="loadFiles"
    />

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传文件到公共空间" width="500px" @close="handleUploadDialogClose">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="选择文件">
          <div class="upload-area" @click="triggerFileSelect" @dragover.prevent @drop.prevent="handleDrop">
            <input type="file" ref="fileInputRef" style="display: none" @change="handleFileInputChange" />
            <el-icon class="el-icon--upload" :size="32"><UploadFilled /></el-icon>
            <div class="upload-area-text" v-if="!uploadForm.file">点击选择文件或拖拽到此处</div>
            <div class="upload-area-text" v-else>已选择: {{ uploadForm.file.name }}</div>
          </div>
        </el-form-item>
        <el-form-item label="文件分类">
          <el-select v-model="uploadForm.category_id" placeholder="选择分类" style="width: 100%">
            <el-option
              v-for="cat in categories"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            >
              <el-icon v-if="cat.icon"><component :is="cat.icon" /></el-icon>
              <span style="margin-left: 8px">{{ cat.name }}</span>
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="uploadFile" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>

    <!-- 分享对话框 -->
    <el-dialog v-model="showShareDialog" title="分享文件" width="500px">
      <el-form :model="shareForm" label-width="100px">
        <el-form-item label="文件名">
          <el-input :value="shareTarget?.origin_name" disabled />
        </el-form-item>
        <el-form-item label="访问密码">
          <el-input v-model="shareForm.password" placeholder="留空则不需要密码" clearable />
        </el-form-item>
        <el-form-item label="有效期">
          <el-select v-model="shareForm.expire_hours" style="width: 100%">
            <el-option label="1小时" :value="1" />
            <el-option label="6小时" :value="6" />
            <el-option label="24小时" :value="24" />
            <el-option label="3天" :value="72" />
            <el-option label="7天" :value="168" />
            <el-option label="永不过期" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="下载次数">
          <el-input-number v-model="shareForm.max_downloads" :min="0" style="width: 100%" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px">0表示不限制下载次数</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showShareDialog = false">取消</el-button>
        <el-button type="primary" @click="createShare" :loading="shareCreating">创建分享</el-button>
      </template>
    </el-dialog>

    <!-- 分享结果对话框 -->
    <el-dialog v-model="showShareResult" title="分享成功" width="500px">
      <el-form label-width="100px">
        <el-form-item label="分享链接">
          <div style="display: flex; gap: 8px;">
            <el-input :value="shareLink" readonly style="flex: 1" />
            <el-button type="primary" @click="copyShareLink">复制</el-button>
          </div>
        </el-form-item>
        <el-form-item label="访问密码" v-if="shareResult?.password">
          <el-input :value="shareResult.password" readonly />
        </el-form-item>
        <el-form-item label="过期时间" v-if="shareResult?.expire_at">
          {{ formatDate(shareResult.expire_at) }}
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" style="margin-top: 10px">
        分享链接可被任何人访问，无需登录账号
      </el-alert>
      <template #footer>
        <el-button type="primary" @click="showShareResult = false">确定</el-button>
      </template>
    </el-dialog>

    <FilePreviewDialog
      v-model="showPreviewDialog"
      :file="previewFile"
      :preview-url="previewUrl"
      :text-request="fetchPreviewText"
      @download="downloadPreviewFile"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, UploadFilled } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import api, { getDirectApiUrl } from '@/utils/api'
import FilePreviewDialog from '@/components/FilePreviewDialog.vue'
import { buildFilePreviewUrl, getFileIcon, getFileIconColor, getFileIconBg, isPreviewable } from '@/utils/file'

const router = useRouter()
const userStore = useUserStore()

const files = ref([])
const categories = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const selectedCategory = ref(null)

// 上传相关
const showUploadDialog = ref(false)
const fileInputRef = ref(null)
const uploadForm = ref({
  file: null,
  category_id: null
})
const uploading = ref(false)
const publicSpaceId = ref(null)

// 分享相关
const showShareDialog = ref(false)
const showShareResult = ref(false)
const shareTarget = ref(null)
const shareCreating = ref(false)
const shareResult = ref(null)
const shareForm = ref({
  password: '',
  expire_hours: 24,
  max_downloads: 0
})
const showPreviewDialog = ref(false)
const previewFile = ref(null)
const previewUrl = ref('')

const shareLink = computed(() => {
  if (!shareResult.value) return ''
  return `${window.location.origin}/files/s/${shareResult.value.share_code}`
})

const goBack = () => {
  router.push('/files')
}

const canDelete = (file) => {
  return file.owner_id === userStore.user?.id || userStore.isAdmin
}

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

const resolveFileIcon = (row) => getFileIcon(row)
const resolveFileIconColor = (row) => getFileIconColor(row)
const resolveFileIconBg = (row) => getFileIconBg(row)
const canPreview = (row) => isPreviewable(row)

const loadPublicSpace = async () => {
  try {
    const space = await api.get('/spaces/public/info')
    publicSpaceId.value = space.id
  } catch (error) {
    console.error('加载公共空间失败:', error)
  }
}

const loadCategories = async () => {
  try {
    categories.value = await api.get('/categories')
  } catch (error) {
    console.error('加载分类失败:', error)
  }
}

const loadFiles = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value
    }
    if (selectedCategory.value) {
      params.category_id = selectedCategory.value
    }

    // 搜索或普通列表
    const result = searchKeyword.value && searchKeyword.value.trim()
      ? await api.get('/files/public/search', { params: { ...params, keyword: searchKeyword.value.trim() } })
      : await api.get('/files/public', { params })

    files.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    console.error('加载文件失败:', error)
    ElMessage.error('加载文件失败')
  } finally {
    loading.value = false
  }
}

const handleCategoryChange = () => {
  page.value = 1
  loadFiles()
}

const searchFiles = () => {
  page.value = 1
  loadFiles()
}

const clearSearch = () => {
  searchKeyword.value = ''
  page.value = 1
  loadFiles()
}

const handleRowClick = (row) => {
  if (canPreview(row)) {
    previewFileItem(row)
  }
}

const previewFileItem = (file) => {
  if (!canPreview(file)) return
  previewFile.value = file
  previewUrl.value = buildFilePreviewUrl(file.id)
  showPreviewDialog.value = true
}

const fetchPreviewText = async () => {
  const response = await fetch(previewUrl.value)
  if (!response.ok) {
    throw new Error('无法读取文件内容')
  }
  return response.text()
}

const downloadFile = (file) => {
  const token = localStorage.getItem('token')
  window.open(`/files/api/files/${file.id}/download?token=${token}`, '_blank')
}

const downloadPreviewFile = () => {
  if (previewFile.value) {
    downloadFile(previewFile.value)
  }
}

const isDirectoryEntry = (file) => {
  if (file.size === 0 && !file.type) return true
  if (file.size === 0 && file.type === '') return true
  return false
}

const readFileToMemory = async (file) => {
  try {
    const data = await file.arrayBuffer()
    return {
      name: file.name,
      size: file.size,
      type: file.type,
      data: data
    }
  } catch (err) {
    throw new Error(`SKIP:${file.name}`)
  }
}

const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = async (event) => {
  const files = event.target.files
  if (files && files.length > 0) {
    const file = files[0]
    if (isDirectoryEntry(file)) {
      ElMessage.warning('请选择文件，不能选择文件夹')
      return
    }
    try {
      const memFile = await readFileToMemory(file)
      uploadForm.value.file = memFile
    } catch (err) {
      console.warn('读取文件失败:', file.name, err)
      ElMessage.error('无法读取文件: ' + (err.message || err))
    }
  }
}

const handleDrop = async (event) => {
  const files = event.dataTransfer.files
  if (files && files.length > 0) {
    const file = files[0]
    if (isDirectoryEntry(file)) {
      ElMessage.warning('请选择文件，不能选择文件夹')
      return
    }
    try {
      const memFile = await readFileToMemory(file)
      uploadForm.value.file = memFile
    } catch (err) {
      console.warn('读取文件失败:', file.name, err)
      ElMessage.error('无法读取文件: ' + (err.message || err))
    }
  }
}

const handleUploadDialogClose = () => {
  if (fileInputRef.value) fileInputRef.value.value = ''
  uploadForm.value = { file: null, category_id: null }
}

const uploadFile = async () => {
  if (!uploadForm.value.file) {
    ElMessage.warning('请选择文件')
    return
  }

  if (!publicSpaceId.value) {
    ElMessage.error('公共空间未初始化')
    return
  }

  uploading.value = true
  try {
    const file = uploadForm.value.file
    const blob = new Blob([file.data], { type: file.type })
    const formData = new FormData()
    formData.append('file', blob, file.name)

    const params = { space_id: publicSpaceId.value }
    if (uploadForm.value.category_id) {
      params.category_id = uploadForm.value.category_id
    }

    const uploadUrl = getDirectApiUrl(`/files/api/files/upload?space_id=${publicSpaceId.value}${uploadForm.value.category_id ? '&category_id=' + uploadForm.value.category_id : ''}`)
    const token = localStorage.getItem('token')
    const response = await fetch(uploadUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || '上传失败')
    }

    ElMessage.success('上传成功')
    showUploadDialog.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
    uploadForm.value = { file: null, category_id: null }
    loadFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploading.value = false
  }
}

const deleteFile = async (file) => {
  try {
    await ElMessageBox.confirm(`确定要删除 "${file.origin_name}" 吗？`, '提示', { type: 'warning' })
    await api.delete(`/files/${file.id}`)
    ElMessage.success('删除成功')
    loadFiles()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const openShareDialog = (file) => {
  shareTarget.value = file
  shareForm.value = {
    password: '',
    expire_hours: 24,
    max_downloads: 0
  }
  showShareDialog.value = true
}

const createShare = async () => {
  if (!shareTarget.value) return
  shareCreating.value = true
  try {
    shareResult.value = await api.post('/shares', {
      file_id: shareTarget.value.id,
      ...shareForm.value
    })
    showShareDialog.value = false
    showShareResult.value = true
  } catch (error) {
    ElMessage.error('创建分享失败')
  } finally {
    shareCreating.value = false
  }
}

const copyShareLink = () => {
  const link = shareLink.value
  if (!link) {
    ElMessage.error('分享链接为空')
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = link
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()

  let success = false
  try {
    success = document.execCommand('copy')
  } catch (e) {
    console.error('复制异常:', e)
  }

  document.body.removeChild(textarea)

  if (success) {
    ElMessage.success('复制成功：' + link)
  } else {
    ElMessage.error('复制失败，请手动复制')
  }
}

onMounted(() => {
  loadPublicSpace()
  loadCategories()
  loadFiles()
})
</script>

<style scoped>
.public-space {
  background: transparent;
}

.page-title {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-main);
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

.toolbar-left {
  display: flex;
  gap: 10px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.category-tabs {
  margin-bottom: 20px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.88);
  border-radius: 22px;
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
  border: 1px solid rgba(218, 229, 247, 0.92);
  backdrop-filter: blur(20px);
}

.file-name {
  display: flex;
  align-items: center;
  cursor: pointer;
  transition: color 0.2s;
  color: var(--text-main);
}

.file-icon-wrapper {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-name:hover {
  color: var(--primary);
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
  font-size: 14px;
  padding: 14px 0;
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid rgba(229, 237, 250, 0.8);
  padding: 14px 0;
}

:deep(.el-table__row) {
  transition: all 0.2s;
  cursor: pointer;
}

:deep(.el-table__row:hover > td) {
  background: rgba(47, 123, 255, 0.035) !important;
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

:deep(.el-pagination) {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-dialog) {
  border-radius: 22px;
}

:deep(.el-dialog__header) {
  padding: 20px 24px;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
}

:deep(.el-dialog__title) {
  font-weight: 800;
  color: var(--text-main);
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__footer) {
  padding: 16px 24px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
}

@media screen and (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }

  .toolbar-left {
    width: 100%;
  }

  .toolbar-right {
    width: 100%;
  }

  .toolbar-right .el-input {
    width: 100% !important;
  }

  .category-tabs {
    overflow-x: auto;
    padding: 12px;
  }

  .category-tabs .el-radio-group {
    flex-wrap: nowrap;
  }

  :deep(.el-table) {
    font-size: 13px;
  }

  :deep(.el-table .el-table__cell) {
    padding: 8px 0;
  }

  :deep(.el-table .el-button) {
    padding: 4px 8px;
    font-size: 12px;
  }

  :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: center;
  }
}

.upload-area {
  border: 2px dashed #d9e1ec;
  border-radius: 12px;
  padding: 24px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafbfe;
}

.upload-area:hover {
  border-color: #5b9aff;
  background: #f0f6ff;
}

.upload-area .el-icon--upload {
  color: #5b9aff;
  margin-bottom: 4px;
}

.upload-area-text {
  color: #8c939d;
  font-size: 13px;
}
</style>
