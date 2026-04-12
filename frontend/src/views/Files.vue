<template>
  <div class="files-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传文件
        </el-button>
        <el-button @click="showFolderDialog = true">
          <el-icon><FolderAdd /></el-icon>
          新建文件夹
        </el-button>
        <el-button v-if="selectedFiles.length" type="danger" @click="batchDelete">
          <el-icon><Delete /></el-icon>
          删除选中 ({{ selectedFiles.length }})
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文件..."
          prefix-icon="Search"
          clearable
          style="width: 250px"
          @keyup.enter="loadFiles"
          @clear="loadFiles"
        />
        <el-button @click="loadFiles">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom: 16px">
      <el-breadcrumb-item @click="navigateTo(null)">根目录</el-breadcrumb-item>
      <el-breadcrumb-item
        v-for="folder in breadcrumbs"
        :key="folder.id"
        @click="navigateTo(folder.id)"
      >
        {{ folder.name }}
      </el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 文件列表 -->
    <el-card v-loading="loading">
      <el-table
        :data="files"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column label="名称" min-width="300">
          <template #default="{ row }">
            <div class="file-item">
              <el-icon class="file-icon" :style="{ color: getFileIconColor(row) }">
                <component :is="getFileIcon(row)" />
              </el-icon>
              <span
                class="file-name"
                @click="handleFileClick(row)"
                style="cursor: pointer"
              >
                {{ row.origin_name || row.name }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="120">
          <template #default="{ row }">
            {{ row.size ? formatSize(row.size) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="修改时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button
                v-if="!row.is_folder"
                size="small"
                @click="downloadFile(row)"
              >
                下载
              </el-button>
              <el-button
                v-if="!row.is_folder"
                size="small"
                @click="previewFile(row)"
              >
                预览
              </el-button>
              <el-dropdown trigger="click">
                <el-button size="small">
                  <el-icon><More /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="renameItem(row)">
                      重命名
                    </el-dropdown-item>
                    <el-dropdown-item @click="moveItem(row)">
                      移动到
                    </el-dropdown-item>
                    <el-dropdown-item divided @click="deleteItem(row)">
                      删除
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
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
          @size-change="loadFiles"
          @current-change="loadFiles"
        />
      </div>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传文件" width="500px">
      <el-upload
        ref="uploadRef"
        :action="uploadUrl"
        :headers="uploadHeaders"
        :data="{ folder_id: currentFolderId }"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :before-upload="beforeUpload"
        multiple
        drag
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或 <em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            单个文件最大 500MB，支持常见文件格式
          </div>
        </template>
      </el-upload>
    </el-dialog>

    <!-- 新建文件夹对话框 -->
    <el-dialog v-model="showFolderDialog" title="新建文件夹" width="400px">
      <el-form @submit.prevent="createFolder">
        <el-form-item label="文件夹名称">
          <el-input v-model="newFolderName" placeholder="请输入文件夹名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFolderDialog = false">取消</el-button>
        <el-button type="primary" @click="createFolder">确定</el-button>
      </template>
    </el-dialog>

    <!-- 重命名对话框 -->
    <el-dialog v-model="showRenameDialog" title="重命名" width="400px">
      <el-form @submit.prevent="doRename">
        <el-form-item label="新名称">
          <el-input v-model="renameValue" placeholder="请输入新名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="doRename">确定</el-button>
      </template>
    </el-dialog>

    <!-- 文件预览对话框 -->
    <el-dialog v-model="showPreviewDialog" :title="previewFile?.origin_name" width="80%">
      <div v-if="previewFileType === 'image'" style="text-align: center">
        <img :src="previewUrl" style="max-width: 100%; max-height: 70vh" />
      </div>
      <iframe
        v-else-if="previewFileType === 'pdf'"
        :src="previewUrl"
        style="width: 100%; height: 70vh; border: none"
      />
      <div v-else style="text-align: center; padding: 40px; color: #909399">
        该文件类型不支持预览，请下载后查看
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const loading = ref(false)
const files = ref([])
const folders = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const currentFolderId = ref(null)
const breadcrumbs = ref([])
const selectedFiles = ref([])

// 对话框状态
const showUploadDialog = ref(false)
const showFolderDialog = ref(false)
const showRenameDialog = ref(false)
const showPreviewDialog = ref(false)

// 表单数据
const newFolderName = ref('')
const renameValue = ref('')
const renameTarget = ref(null)
const previewFileData = ref(null)
const previewUrl = ref('')
const previewFileType = ref('')

// 上传配置
const uploadUrl = computed(() => '/api/files/upload')
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}))

// 加载文件列表
const loadFiles = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      folder_id: currentFolderId.value,
      keyword: searchKeyword.value || undefined
    }
    const res = await api.get('/files', { params })
    files.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('加载文件失败:', error)
  } finally {
    loading.value = false
  }
}

// 加载文件夹树
const loadFolders = async () => {
  try {
    const res = await api.get('/files/folders/tree')
    folders.value = res
  } catch (error) {
    console.error('加载文件夹失败:', error)
  }
}

// 导航到文件夹
const navigateTo = (folderId) => {
  currentFolderId.value = folderId
  page.value = 1
  loadFiles()
}

// 处理文件点击
const handleFileClick = (row) => {
  if (row.is_folder) {
    navigateTo(row.id)
  }
}

// 获取文件图标
const getFileIcon = (row) => {
  if (row.is_folder) return 'Folder'
  const ext = row.ext?.toLowerCase()
  const iconMap = {
    'pdf': 'Document',
    'doc': 'Document',
    'docx': 'Document',
    'xls': 'Document',
    'xlsx': 'Document',
    'ppt': 'Document',
    'pptx': 'Document',
    'jpg': 'Picture',
    'jpeg': 'Picture',
    'png': 'Picture',
    'gif': 'Picture',
    'webp': 'Picture',
    'mp3': 'Headset',
    'mp4': 'VideoCamera',
    'zip': 'Files',
    'rar': 'Files',
    '7z': 'Files',
    'txt': 'Notebook',
    'md': 'Notebook'
  }
  return iconMap[ext] || 'Document'
}

// 获取文件图标颜色
const getFileIconColor = (row) => {
  if (row.is_folder) return '#E6A23C'
  const ext = row.ext?.toLowerCase()
  const colorMap = {
    'pdf': '#F56C6C',
    'doc': '#409EFF',
    'docx': '#409EFF',
    'xls': '#67C23A',
    'xlsx': '#67C23A',
    'ppt': '#E6A23C',
    'pptx': '#E6A23C',
    'jpg': '#67C23A',
    'jpeg': '#67C23A',
    'png': '#67C23A',
    'gif': '#67C23A',
    'mp3': '#909399',
    'mp4': '#909399'
  }
  return colorMap[ext] || '#909399'
}

// 格式化文件大小
const formatSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 创建文件夹
const createFolder = async () => {
  if (!newFolderName.value.trim()) {
    ElMessage.warning('请输入文件夹名称')
    return
  }
  try {
    await api.post('/files/folders', {
      name: newFolderName.value,
      parent_id: currentFolderId.value
    })
    ElMessage.success('文件夹创建成功')
    showFolderDialog.value = false
    newFolderName.value = ''
    loadFolders()
    loadFiles()
  } catch (error) {
    console.error('创建文件夹失败:', error)
  }
}

// 上传前检查
const beforeUpload = (file) => {
  const maxSize = 500 * 1024 * 1024 // 500MB
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 500MB')
    return false
  }
  return true
}

// 上传成功
const handleUploadSuccess = (response) => {
  ElMessage.success('上传成功')
  showUploadDialog.value = false
  loadFiles()
}

// 上传失败
const handleUploadError = (error) => {
  ElMessage.error('上传失败')
}

// 下载文件
const downloadFile = (file) => {
  const url = `/api/files/${file.id}/download`
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', file.origin_name)
  link.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('token')}`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

// 预览文件
const previewFileItem = async (file) => {
  previewFileData.value = file
  previewUrl.value = `/api/files/${file.id}/preview`

  const ext = file.ext?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext)) {
    previewFileType.value = 'image'
  } else if (ext === 'pdf') {
    previewFileType.value = 'pdf'
  } else {
    previewFileType.value = 'unsupported'
  }

  showPreviewDialog.value = true
}

// 重命名
const renameItem = (row) => {
  renameTarget.value = row
  renameValue.value = row.origin_name || row.name
  showRenameDialog.value = true
}

// 执行重命名
const doRename = async () => {
  if (!renameValue.value.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  try {
    if (renameTarget.value.is_folder) {
      await api.put(`/files/folders/${renameTarget.value.id}`, { name: renameValue.value })
    } else {
      // 文件重命名接口待实现
      ElMessage.info('文件重命名功能开发中')
    }
    showRenameDialog.value = false
    loadFiles()
    loadFolders()
  } catch (error) {
    console.error('重命名失败:', error)
  }
}

// 删除项目
const deleteItem = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除吗？', '确认删除', { type: 'warning' })
    if (row.is_folder) {
      await api.delete(`/files/folders/${row.id}`)
    } else {
      await api.delete(`/files/${row.id}`)
    }
    ElMessage.success('删除成功')
    loadFiles()
    loadFolders()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
    }
  }
}

// 移动项目
const moveItem = (row) => {
  ElMessage.info('移动功能开发中')
}

// 选择变化
const handleSelectionChange = (selection) => {
  selectedFiles.value = selection
}

// 批量删除
const batchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedFiles.value.length} 个文件吗？`, '确认删除', { type: 'warning' })
    for (const file of selectedFiles.value) {
      await api.delete(`/files/${file.id}`)
    }
    ElMessage.success('删除成功')
    loadFiles()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
    }
  }
}

onMounted(() => {
  loadFiles()
  loadFolders()
})
</script>

<style scoped>
.file-item {
  display: flex;
  align-items: center;
}

.file-icon {
  font-size: 24px;
  margin-right: 8px;
}

.file-name {
  cursor: pointer;
}

.file-name:hover {
  color: #409EFF;
}
</style>
