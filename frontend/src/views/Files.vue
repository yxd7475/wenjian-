<template>
  <div class="files-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button v-if="currentFolderId" @click="goBack">
          <el-icon><Back /></el-icon>
          返回上层
        </el-button>
        <el-button type="primary" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传文件
        </el-button>
        <el-button type="primary" plain @click="triggerFolderUpload">
          <el-icon><FolderAdd /></el-icon>
          上传文件夹
        </el-button>
        <input type="file" ref="folderInputRef" webkitdirectory directory multiple style="display: none" @change="handleFolderSelect" />
        <el-button @click="showFolderDialog = true">
          <el-icon><FolderAdd /></el-icon>
          新建文件夹
        </el-button>
        <el-button v-if="selectedItems.length" type="danger" @click="batchDelete">
          <el-icon><Delete /></el-icon>
          删除 ({{ selectedItems.length }})
        </el-button>
        <el-button v-if="selectedItems.length && !hasFolderSelected" @click="batchDownload">
          <el-icon><Download /></el-icon>
          批量下载
        </el-button>
      </div>
      <div class="toolbar-right">
        <!-- 高级搜索 -->
        <el-popover placement="bottom" :width="400" trigger="click" v-model:visible="showAdvancedSearch">
          <template #reference>
            <el-button :type="hasAdvancedFilters ? 'primary' : 'default'">
              <el-icon><Search /></el-icon>
              高级搜索
            </el-button>
          </template>
          <el-form label-width="80px" size="small">
            <el-form-item label="文件名">
              <el-input v-model="advancedFilters.keyword" placeholder="文件名关键词" clearable />
            </el-form-item>
            <el-form-item label="文件类型">
              <el-select v-model="advancedFilters.ext" placeholder="全部类型" clearable style="width: 100%">
                <el-option label="图片" value="image" />
                <el-option label="文档" value="document" />
                <el-option label="视频" value="video" />
                <el-option label="音频" value="audio" />
                <el-option label="压缩包" value="archive" />
              </el-select>
            </el-form-item>
            <el-form-item label="上传时间">
              <el-date-picker
                v-model="advancedFilters.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="文件大小">
              <el-select v-model="advancedFilters.sizeRange" placeholder="全部大小" clearable style="width: 100%">
                <el-option label="小于 1MB" value="small" />
                <el-option label="1MB - 10MB" value="medium" />
                <el-option label="10MB - 100MB" value="large" />
                <el-option label="大于 100MB" value="huge" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="applyAdvancedSearch">搜索</el-button>
              <el-button @click="resetAdvancedSearch">重置</el-button>
            </el-form-item>
          </el-form>
        </el-popover>
        <!-- 视图切换 -->
        <el-button-group>
          <el-button :type="viewMode === 'list' ? 'primary' : 'default'" @click="viewMode = 'list'">
            <el-icon><List /></el-icon>
          </el-button>
          <el-button :type="viewMode === 'grid' ? 'primary' : 'default'" @click="viewMode = 'grid'">
            <el-icon><Grid /></el-icon>
          </el-button>
        </el-button-group>
        <el-button @click="$router.push('/trash')">
          <el-icon><Delete /></el-icon>
          回收站
        </el-button>
      </div>
    </div>

    <!-- 面包屑 + 排序 -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item @click="navigateTo(null)" style="cursor: pointer">根目录</el-breadcrumb-item>
        <el-breadcrumb-item
          v-for="folder in breadcrumbs"
          :key="folder.id"
          @click="navigateTo(folder.id, folder.name)"
          style="cursor: pointer"
        >
          {{ folder.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>
      <div style="display: flex; gap: 8px; align-items: center">
        <span style="color: #909399; font-size: 13px">排序：</span>
        <el-select v-model="sortBy" size="small" style="width: 100px" @change="loadFiles">
          <el-option label="名称" value="name" />
          <el-option label="大小" value="size" />
          <el-option label="时间" value="time" />
        </el-select>
        <el-button size="small" @click="toggleSortOrder">
          <el-icon><component :is="sortOrder === 'asc' ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 骨架屏 -->
    <template v-if="loading">
      <el-card v-if="viewMode === 'list'">
        <el-skeleton :rows="5" animated />
      </el-card>
      <div v-else class="grid-view">
        <el-card v-for="i in 8" :key="i" class="grid-item-skeleton">
          <el-skeleton animated>
            <template #template>
              <el-skeleton-item variant="image" style="height: 120px" />
              <div style="padding: 14px">
                <el-skeleton-item variant="h3" style="width: 80%" />
                <el-skeleton-item variant="text" style="margin-top: 8px" />
              </div>
            </template>
          </el-skeleton>
        </el-card>
      </div>
    </template>

    <!-- 空状态 -->
    <el-empty v-else-if="!loading && files.length === 0" description="暂无文件">
      <el-button type="primary" @click="showUploadDialog = true">上传文件</el-button>
    </el-empty>

    <!-- 列表视图 -->
    <el-card v-else-if="viewMode === 'list'">
      <el-table
        ref="tableRef"
        :data="sortedFiles"
        @selection-change="handleSelectionChange"
        @row-contextmenu="handleContextMenu"
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column label="名称" min-width="300">
          <template #default="{ row }">
            <div class="file-item">
              <div class="file-icon-wrapper" :style="{ background: resolveFileIconBg(row) }">
                <el-icon :size="20" color="#fff">
                  <component :is="resolveFileIcon(row)" />
                </el-icon>
              </div>
              <span class="file-name" @click="handleFileClick(row)" style="cursor: pointer">
                {{ row.origin_name || row.name }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ row.size ? formatSize(row.size) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="上传者" width="100">
          <template #default="{ row }">
            {{ row.owner?.real_name || row.owner?.username || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="修改时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button v-if="!row.is_folder" size="small" @click="downloadFile(row)">下载</el-button>
              <el-button v-if="canPreview(row)" size="small" @click="previewFileItem(row)">预览</el-button>
              <el-dropdown trigger="click">
                <el-button size="small">
                  <el-icon><More /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="!row.is_folder" @click="openShareDialog(row)"><el-icon><Share /></el-icon>分享</el-dropdown-item>
                    <el-dropdown-item @click="renameItem(row)"><el-icon><Edit /></el-icon>重命名</el-dropdown-item>
                    <el-dropdown-item v-if="!row.is_folder" @click="showMoveDialog(row)"><el-icon><Rank /></el-icon>移动到</el-dropdown-item>
                    <el-dropdown-item v-if="!row.is_folder" @click="showCopyDialog(row)"><el-icon><CopyDocument /></el-icon>复制到</el-dropdown-item>
                    <el-dropdown-item divided @click="deleteItem(row)"><el-icon><Delete /></el-icon>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
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

    <!-- 卡片视图 -->
    <div v-else class="grid-view">
      <el-card
        v-for="file in sortedFiles"
        :key="file.id"
        class="grid-item"
        :class="{ 'grid-item-selected': selectedItems.includes(file) }"
        @click="toggleSelect(file)"
        @dblclick="handleFileClick(file)"
        @contextmenu.prevent="handleContextMenu(file, $event)"
      >
        <div class="grid-item-content">
          <div class="grid-icon">
            <div class="file-icon-wrapper-lg" :style="{ background: resolveFileIconBg(file) }">
              <el-icon :size="36" color="#fff">
                <component :is="resolveFileIcon(file)" />
              </el-icon>
            </div>
          </div>
          <div class="grid-info">
            <div class="grid-name">{{ file.origin_name || file.name }}</div>
            <div class="grid-meta">
              <span v-if="file.size">{{ formatSize(file.size) }}</span>
              <span>{{ formatDate(file.updated_at) }}</span>
            </div>
          </div>
        </div>
        <div class="grid-actions" @click.stop>
          <el-button v-if="!file.is_folder" size="small" text @click="downloadFile(file)">
            <el-icon><Download /></el-icon>
          </el-button>
          <el-button v-if="canPreview(file)" size="small" text @click="previewFileItem(file)">
            <el-icon><View /></el-icon>
          </el-button>
          <el-button size="small" text @click="deleteItem(file)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 右键菜单 -->
    <div v-show="contextMenuVisible" class="context-menu" :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }">
      <div class="context-menu-item" @click="contextMenuAction('open')">
        <el-icon><FolderOpened /></el-icon> 打开
      </div>
      <div class="context-menu-item" v-if="!contextMenuTarget?.is_folder" @click="contextMenuAction('download')">
        <el-icon><Download /></el-icon> 下载
      </div>
      <div class="context-menu-item" v-if="canPreview(contextMenuTarget)" @click="contextMenuAction('preview')">
        <el-icon><View /></el-icon> 预览
      </div>
      <div class="context-menu-item" v-if="!contextMenuTarget?.is_folder" @click="contextMenuAction('share')">
        <el-icon><Share /></el-icon> 分享
      </div>
      <div class="context-menu-divider"></div>
      <div class="context-menu-item" @click="contextMenuAction('rename')">
        <el-icon><Edit /></el-icon> 重命名
      </div>
      <div class="context-menu-item" v-if="!contextMenuTarget?.is_folder" @click="contextMenuAction('move')">
        <el-icon><Rank /></el-icon> 移动到
      </div>
      <div class="context-menu-item" v-if="!contextMenuTarget?.is_folder" @click="contextMenuAction('copy')">
        <el-icon><CopyDocument /></el-icon> 复制到
      </div>
      <div class="context-menu-divider"></div>
      <div class="context-menu-item context-menu-danger" @click="contextMenuAction('delete')">
        <el-icon><Delete /></el-icon> 删除
      </div>
    </div>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传文件" width="600px" @close="clearUploadFiles">
      <div class="upload-area" @click="triggerFileSelect" @dragover.prevent @drop.prevent="handleDrop">
        <input type="file" ref="fileInputRef" multiple style="display: none" @change="handleFileInputChange" />
        <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件或文件夹到此处，或 <em>点击选择文件</em></div>
      </div>
      <div v-if="selectedUploadFiles.length > 0" class="selected-files">
        <div v-for="(f, idx) in selectedUploadFiles" :key="idx" class="selected-file-item">
          <span class="file-name">{{ f.name }}</span>
          <span class="file-size">{{ formatSize(f.size) }}</span>
          <el-button type="danger" text size="small" @click="removeUploadFile(idx)">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>
      <div v-if="uploadProgress > 0" class="upload-progress">
        <el-progress :percentage="uploadProgress" :status="uploadStatus" />
      </div>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="doUploadFiles" :loading="uploading" :disabled="selectedUploadFiles.length === 0">
          {{ uploading ? '上传中...' : '开始上传' }}
        </el-button>
      </template>
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

    <!-- 移动/复制对话框 -->
    <el-dialog v-model="showMoveCopyDialog" :title="moveCopyTitle" width="400px">
      <el-tree
        :data="folderTreeData"
        :props="{ label: 'name', children: 'children' }"
        node-key="id"
        highlight-current
        @current-change="handleTreeSelect"
        default-expand-all
      />
      <template #footer>
        <el-button @click="showMoveCopyDialog = false">取消</el-button>
        <el-button type="primary" @click="doMoveCopy">确定</el-button>
      </template>
    </el-dialog>

    <FilePreviewDialog
      v-model="showPreviewDialog"
      :file="previewFile"
      :preview-url="previewUrl"
      @download="downloadPreviewFile"
    />

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
        <el-form-item label="下载限制" v-if="shareResult?.max_downloads">
          {{ shareResult.max_downloads }} 次
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" style="margin-top: 10px">
        分享链接可被任何人访问，无需登录账号
      </el-alert>
      <template #footer>
        <el-button type="primary" @click="showShareResult = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Folder, ArrowUp, ArrowDown, Share, Close, UploadFilled, Upload, FolderAdd
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import api, { getDirectApiUrl } from '@/utils/api'
import FilePreviewDialog from '@/components/FilePreviewDialog.vue'
import { buildFilePreviewUrl, getFileIcon, getFileIconColor, getFileIconBg, getFileIconBgFolder, isPreviewable } from '@/utils/file'

const userStore = useUserStore()
const loading = ref(false)
const files = ref([])
const folders = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const currentFolderId = ref(null)
const breadcrumbs = ref([])
const selectedItems = ref([])
const tableRef = ref(null)
const personalSpaceId = ref(null)

// 视图和排序
const viewMode = ref(localStorage.getItem('viewMode') || 'list')
const sortBy = ref('time')
const sortOrder = ref('desc')

// 高级搜索
const showAdvancedSearch = ref(false)
const advancedFilters = ref({
  keyword: '',
  ext: '',
  dateRange: null,
  sizeRange: ''
})

// 对话框状态
const showUploadDialog = ref(false)
const showFolderDialog = ref(false)
const showRenameDialog = ref(false)
const showPreviewDialog = ref(false)
const showMoveCopyDialog = ref(false)
const showTrashDialog = ref(false)
const trashFiles = ref([])
const trashLoading = ref(false)

// 表单数据
const newFolderName = ref('')
const renameValue = ref('')
const renameTarget = ref(null)
const previewFile = ref(null)
const previewUrl = ref('')

// 移动/复制相关
const moveCopyMode = ref('move')
const moveCopyTarget = ref(null)
const selectedTargetFolder = ref(null)

// 上传相关
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref('')

// 右键菜单
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuTarget = ref(null)

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
const serverIp = ref(null)

// 获取服务器 IP
const fetchServerIp = async () => {
  if (serverIp.value) return
  try {
    const data = await api.get('/auth/server-info')
    if (data.local_ips && data.local_ips.length > 0) {
      const preferredIp = data.local_ips.find(ip => !ip.startsWith('172.') && !ip.startsWith('169.254.'))
      serverIp.value = preferredIp || data.local_ips[0]
    }
  } catch (error) {
    console.error('获取服务器 IP 失败:', error)
  }
}

const shareLink = computed(() => {
  if (!shareResult.value) return ''
  return `${window.location.origin}/files/s/${shareResult.value.share_code}`
})

// 计算属性
const hasFolderSelected = computed(() => selectedItems.value.some(item => item.is_folder))
const moveCopyTitle = computed(() => moveCopyMode.value === 'move' ? '移动到' : '复制到')
const hasAdvancedFilters = computed(() => {
  return advancedFilters.value.keyword || advancedFilters.value.ext ||
         advancedFilters.value.dateRange || advancedFilters.value.sizeRange
})

const folderTreeData = computed(() => {
  const buildTree = (folders, parentId = null) => {
    return folders.filter(f => f.parent_id === parentId).map(f => ({
      ...f,
      children: buildTree(folders, f.id)
    }))
  }
  return [{ id: null, name: '根目录', children: buildTree(folders.value) }]
})

const sortedFiles = computed(() => {
  const items = [...files.value]
  const order = sortOrder.value === 'asc' ? 1 : -1
  items.sort((a, b) => {
    if (a.is_folder && !b.is_folder) return -1
    if (!a.is_folder && b.is_folder) return 1
    if (sortBy.value === 'name') return order * (a.origin_name || a.name).localeCompare(b.origin_name || b.name)
    if (sortBy.value === 'size') return order * ((a.size || 0) - (b.size || 0))
    return order * (new Date(a.updated_at) - new Date(b.updated_at))
  })
  return items
})

// 方法
const canPreview = (row) => !row?.is_folder && isPreviewable(row)

const toggleSortOrder = () => {
  sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
}

const resolveFileIcon = (row) => row?.is_folder ? Folder : getFileIcon(row)
const resolveFileIconColor = (row) => row?.is_folder ? '#fff' : getFileIconColor(row)
const resolveFileIconBg = (row) => row?.is_folder ? getFileIconBgFolder() : getFileIconBg(row)

const formatSize = (bytes) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadPersonalSpace = async () => {
  try {
    const spaces = await api.get('/spaces')
    const personalSpace = spaces.find(s => s.space_type === 'personal')
    if (personalSpace) {
      personalSpaceId.value = personalSpace.id
    }
  } catch (error) {
    console.error('获取个人空间失败:', error)
  }
}

const loadFiles = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      folder_id: currentFolderId.value || undefined,
      keyword: advancedFilters.value.keyword || undefined,
      space_id: personalSpaceId.value || undefined
    }
    const foldersRes = await api.get('/files/folders/tree', { params: { space_id: personalSpaceId.value } })
    const allFolders = flattenFolders(foldersRes || [])
    const currentFolders = allFolders
      .filter(f => f.parent_id === currentFolderId.value)
      .map(f => ({ ...f, is_folder: true, origin_name: f.name }))

    const res = await api.get('/files', { params })
    files.value = [...currentFolders, ...res.items]
    total.value = res.total + currentFolders.length
  } catch (error) {
    console.error('加载文件失败:', error)
  } finally {
    loading.value = false
  }
}

const flattenFolders = (folders, result = []) => {
  for (const folder of folders) {
    result.push(folder)
    if (folder.children?.length > 0) flattenFolders(folder.children, result)
  }
  return result
}

const goBack = () => {
  if (breadcrumbs.value.length > 0) {
    breadcrumbs.value.pop()
    currentFolderId.value = breadcrumbs.value.length > 0 ? breadcrumbs.value[breadcrumbs.value.length - 1].id : null
    page.value = 1
    loadFiles()
  }
}

const loadFolders = async () => {
  try {
    folders.value = await api.get('/files/folders/tree', { params: { space_id: personalSpaceId.value } }) || []
  } catch (error) {
    console.error('加载文件夹失败:', error)
  }
}

const navigateTo = (folderId, folderName = null) => {
  if (folderId === null) {
    breadcrumbs.value = []
  } else if (folderName) {
    const idx = breadcrumbs.value.findIndex(f => f.id === folderId)
    breadcrumbs.value = idx >= 0 ? breadcrumbs.value.slice(0, idx + 1) : [...breadcrumbs.value, { id: folderId, name: folderName }]
  }
  currentFolderId.value = folderId
  page.value = 1
  loadFiles()
}

const handleFileClick = (row) => {
  if (row.is_folder) {
    breadcrumbs.value.push({ id: row.id, name: row.name })
    currentFolderId.value = row.id
    page.value = 1
    loadFiles()
    return
  }
  if (canPreview(row)) {
    previewFileItem(row)
  }
}

const toggleSelect = (file) => {
  const idx = selectedItems.value.indexOf(file)
  if (idx >= 0) selectedItems.value.splice(idx, 1)
  else selectedItems.value.push(file)
}

// 右键菜单
const handleContextMenu = (row, event) => {
  contextMenuTarget.value = row
  contextMenuX.value = event?.clientX || 0
  contextMenuY.value = event?.clientY || 0
  contextMenuVisible.value = true
}

const hideContextMenu = () => {
  contextMenuVisible.value = false
}

const contextMenuAction = (action) => {
  hideContextMenu()
  const row = contextMenuTarget.value
  if (!row) return
  switch (action) {
    case 'open': handleFileClick(row); break
    case 'download': downloadFile(row); break
    case 'preview': previewFileItem(row); break
    case 'share': openShareDialog(row); break
    case 'rename': renameItem(row); break
    case 'move': showMoveDialog(row); break
    case 'copy': showCopyDialog(row); break
    case 'delete': deleteItem(row); break
  }
}

// 分享相关方法
const openShareDialog = (file) => {
  if (file.is_folder) {
    ElMessage.warning('暂不支持分享文件夹')
    return
  }
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
    await fetchServerIp()
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
  console.log('复制链接:', link)

  if (!link) {
    ElMessage.error('分享链接为空')
    return
  }

  // 创建 textarea 元素
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
    console.log('复制结果:', success)
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

const createFolder = async () => {
  if (!newFolderName.value.trim()) {
    ElMessage.warning('请输入文件夹名称')
    return
  }
  try {
    await api.post('/files/folders', { name: newFolderName.value, parent_id: currentFolderId.value, space_id: personalSpaceId.value })
    ElMessage.success('文件夹创建成功')
    showFolderDialog.value = false
    newFolderName.value = ''
    loadFolders()
    loadFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  }
}

const beforeUpload = (file) => {
  return true
}

const fileInputRef = ref(null)
const selectedUploadFiles = ref([])

const isDirectoryEntry = (file) => {
  const name = (file.name || '').toLowerCase()
  const ext = name.includes('.') ? name.split('.').pop() : ''
  if (ext) return false
  return file.size === 0 && !file.type
}

const traverseFileTree = (entry, path = '') => {
  return new Promise((resolve) => {
    if (entry.isFile) {
      entry.file((file) => {
        const reader = new FileReader()
        reader.onload = () => {
          resolve([{
            name: file.name,
            size: file.size,
            type: file.type,
            data: reader.result,
            _relativePath: path + file.name
          }])
        }
        reader.onerror = () => resolve([])
        reader.readAsArrayBuffer(file)
      }, () => resolve([]))
    } else if (entry.isDirectory) {
      const dirReader = entry.createReader()
      const allEntries = []
      const readBatch = () => {
        dirReader.readEntries((entries) => {
          if (entries.length === 0) {
            Promise.all(allEntries.map(e => traverseFileTree(e, path + entry.name + '/')))
              .then(results => resolve(results.flat()))
          } else {
            allEntries.push(...entries)
            readBatch()
          }
        }, () => resolve([]))
      }
      readBatch()
    } else {
      resolve([])
    }
  })
}

const readFileToMemory = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      if (reader.error) {
        reject(reader.error)
        return
      }
      resolve({
        name: file.name,
        size: file.size,
        type: file.type,
        data: reader.result
      })
    }
    reader.readAsArrayBuffer(file)
  })
}

const readFilesConcurrently = async (files, concurrency = 8) => {
  const allResults = []
  for (let i = 0; i < files.length; i += concurrency) {
    const batch = files.slice(i, i + concurrency)
    const batchResults = await Promise.allSettled(
      batch.map(f => readFileToMemory(f).catch(() => null))
    )
    allResults.push(...batchResults)
  }
  return allResults
}

const triggerFileSelect = () => {
  fileInputRef.value?.click()
}

const handleFileInputChange = (event) => {
  const fileList = event.target.files
  if (!fileList || fileList.length === 0) return

  const entries = Array.from(fileList)
  const fileEntries = entries.filter(f => !isDirectoryEntry(f))
  const skippedDirs = entries.length - fileEntries.length

  fileEntries.forEach(f => {
    f._isRawFile = true
    selectedUploadFiles.value.push(f)
  })

  if (skippedDirs > 0) {
    ElMessage.info(`已跳过 ${skippedDirs} 个文件夹`)
  }
}

const handleDrop = async (event) => {
  const items = event.dataTransfer.items
  if (items && items.length > 0) {
    let hasFolder = false
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry?.()
      if (entry && entry.isDirectory) {
        hasFolder = true
        break
      }
    }

    if (hasFolder) {
      const allFiles = []
      for (let i = 0; i < items.length; i++) {
        const entry = items[i].webkitGetAsEntry?.()
        if (!entry) continue
        if (entry.isDirectory) {
          const files = await traverseFileTree(entry)
          allFiles.push(...files)
        } else if (entry.isFile) {
          const memFile = await new Promise(resolve => {
            entry.file((file) => {
              const reader = new FileReader()
              reader.onload = () => resolve({
                name: file.name,
                size: file.size,
                type: file.type,
                data: reader.result,
                _relativePath: file.name
              })
              reader.onerror = () => resolve(null)
              reader.readAsArrayBuffer(file)
            }, () => resolve(null))
          })
          if (memFile) {
            allFiles.push(memFile)
          }
        }
      }
      if (allFiles.length > 0) {
        await uploadDroppedFolder(allFiles)
      } else {
        ElMessage.warning('文件夹中没有可上传的文件')
      }
      return
    }
  }

  const files = event.dataTransfer.files
  if (files && files.length > 0) {
    const entries = Array.from(files)
    const fileEntries = entries.filter(f => !isDirectoryEntry(f))
    const skippedDirs = entries.length - fileEntries.length

    fileEntries.forEach(f => {
      f._isRawFile = true
      selectedUploadFiles.value.push(f)
    })

    if (skippedDirs > 0) {
      ElMessage.info(`已跳过 ${skippedDirs} 个文件夹`)
    }
  }
}

const uploadDroppedFolder = async (fileList) => {
  folderUploading.value = true

  try {
    const formData = new FormData()
    const pathList = []
    let readErrors = 0

    for (const memFile of fileList) {
      const relativePath = memFile._relativePath || memFile.webkitRelativePath || memFile.name
      if (!memFile.data) {
        readErrors++
        continue
      }
      try {
        const blob = new Blob([memFile.data], { type: memFile.type || 'application/octet-stream' })
        formData.append('files', blob, memFile.name)
        pathList.push(relativePath)
      } catch (err) {
        readErrors++
      }
    }

    if (pathList.length === 0) {
      ElMessage.warning('文件夹中没有可上传的文件')
      folderUploading.value = false
      return
    }

    const skipInfo = readErrors > 0 ? `（已跳过 ${readErrors} 个不可读取项）` : ''
    const uploadMsg = ElMessage({
      message: `正在上传 ${pathList.length} 个文件${skipInfo}...`,
      type: 'info',
      duration: 0
    })

    formData.append('paths', JSON.stringify(pathList))

    const params = new URLSearchParams()
    if (personalSpaceId.value) params.append('space_id', personalSpaceId.value)

    const token = localStorage.getItem('token')
    const response = await fetch(getDirectApiUrl(`/files/api/files/upload-folder?${params.toString()}`), {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })

    uploadMsg.close()
    const result = await response.json()
    ElMessage.success(result.message || `成功上传 ${result.uploaded_count} 个文件`)
    loadFiles()
  } catch (error) {
    console.error('文件夹上传失败:', error)
    ElMessage.error('文件夹上传失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    folderUploading.value = false
  }
}

const removeUploadFile = (idx) => {
  selectedUploadFiles.value.splice(idx, 1)
}

const clearUploadFiles = () => {
  selectedUploadFiles.value = []
  uploadProgress.value = 0
  uploadStatus.value = ''
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const doUploadFiles = async () => {
  if (selectedUploadFiles.value.length === 0) return
  uploading.value = true
  uploadProgress.value = 0
  uploadStatus.value = ''

  const total = selectedUploadFiles.value.length
  let completed = 0

  for (const fileEntry of selectedUploadFiles.value) {
    try {
      const formData = new FormData()
      if (fileEntry._isRawFile) {
        formData.append('file', fileEntry, fileEntry.name)
      } else {
        const blob = new Blob([fileEntry.data], { type: fileEntry.type || 'application/octet-stream' })
        formData.append('file', blob, fileEntry.name)
      }

      const params = new URLSearchParams()
      if (currentFolderId.value) params.append('folder_id', currentFolderId.value)
      if (personalSpaceId.value) params.append('space_id', personalSpaceId.value)

      const token = localStorage.getItem('token')
      const url = getDirectApiUrl(`/files/api/files/upload?${params.toString()}`)

      await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', url, true)
        xhr.setRequestHeader('Authorization', `Bearer ${token}`)
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const currentPct = e.loaded / e.total
            uploadProgress.value = Math.round(((completed + currentPct) / total) * 100)
          }
        }
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve()
          } else {
            let detail = `上传失败: ${xhr.status}`
            try { const d = JSON.parse(xhr.responseText); if (d.detail) detail = d.detail } catch (_) {}
            reject(new Error(detail))
          }
        }
        xhr.onerror = () => reject(new Error('网络错误'))
        xhr.ontimeout = () => reject(new Error('上传超时'))
        xhr.send(formData)
      })

      completed++
      uploadProgress.value = Math.round((completed / total) * 100)
    } catch (error) {
      console.error('上传文件失败:', fileEntry.name, error)
    }
  }

  uploading.value = false
  uploadStatus.value = 'success'
  ElMessage.success(`成功上传 ${completed}/${total} 个文件`)
  showUploadDialog.value = false
  if (fileInputRef.value) fileInputRef.value.value = ''
  selectedUploadFiles.value = []
  loadFiles()
}

const handleUploadProgress = (event) => {
  uploadProgress.value = Math.round(event.percent)
  uploadStatus.value = uploadProgress.value >= 100 ? 'success' : ''
}

const submitUpload = () => {
  doUploadFiles()
}

const handleUploadSuccess = () => {
  uploading.value = false
  uploadProgress.value = 100
  uploadStatus.value = 'success'
  ElMessage.success('上传成功')
  showUploadDialog.value = false
  pendingFiles.value = []
  loadFiles()
}

const handleUploadError = () => {
  uploading.value = false
  uploadStatus.value = 'exception'
  ElMessage.error('上传失败')
}

const folderInputRef = ref(null)
const folderUploading = ref(false)

const triggerFolderUpload = () => {
  folderInputRef.value?.click()
}

const handleFolderSelect = async (event) => {
  const fileList = event.target.files
  if (!fileList || fileList.length === 0) return

  folderUploading.value = true

  try {
    const entries = Array.from(fileList)
    const fileEntries = entries.filter(f => !isDirectoryEntry(f))
    const skippedDirs = entries.length - fileEntries.length
    const filePaths = fileEntries.map(f => f.webkitRelativePath || f.name)

    const results = await readFilesConcurrently(fileEntries)

    const formData = new FormData()
    const pathList = []
    let readErrors = 0

    results.forEach((r, idx) => {
      if (r.status === 'fulfilled' && r.value) {
        const blob = new Blob([r.value.data], { type: r.value.type || 'application/octet-stream' })
        formData.append('files', blob, r.value.name)
        pathList.push(filePaths[idx])
      } else {
        readErrors++
      }
    })

    if (pathList.length === 0) {
      ElMessage.warning('文件夹中没有可上传的文件')
      folderUploading.value = false
      return
    }

    const skipInfo = (skippedDirs + readErrors) > 0 ? `（已跳过 ${skippedDirs + readErrors} 个不可读取项）` : ''
    const uploadMsg = ElMessage({
      message: `正在上传 ${pathList.length} 个文件${skipInfo}...`,
      type: 'info',
      duration: 0
    })

    formData.append('paths', JSON.stringify(pathList))

    const params = new URLSearchParams()
    if (personalSpaceId.value) params.append('space_id', personalSpaceId.value)

    const token = localStorage.getItem('token')
    const response = await fetch(getDirectApiUrl(`/files/api/files/upload-folder?${params.toString()}`), {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    })

    uploadMsg.close()
    const result = await response.json()
    ElMessage.success(result.message || `成功上传 ${result.uploaded_count} 个文件`)
    loadFiles()
  } catch (error) {
    console.error('文件夹上传失败:', error)
    ElMessage.error('文件夹上传失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    folderUploading.value = false
    if (folderInputRef.value) folderInputRef.value.value = ''
  }
}

const downloadFile = async (file) => {
  try {
    const response = await fetch(`/files/api/files/${file.id}/download`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
    if (!response.ok) throw new Error('下载失败')
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.origin_name
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const batchDownload = async () => {
  const fileIds = selectedItems.value.filter(item => !item.is_folder).map(item => item.id)
  if (!fileIds.length) return ElMessage.warning('请选择要下载的文件')
  try {
    const response = await fetch('/files/api/files/batch-download', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ file_ids: fileIds })
    })
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `download_${Date.now()}.zip`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const previewFileItem = async (file) => {
  previewFile.value = file
  previewUrl.value = buildFilePreviewUrl(file.id)
  showPreviewDialog.value = true
}

const fetchPreviewText = async () => {
  if (!previewUrl.value) return ''
  const response = await fetch(previewUrl.value)
  if (!response.ok) {
    throw new Error('无法读取文件内容')
  }
  return response.text()
}

const downloadPreviewFile = () => {
  if (previewFile.value) {
    downloadFile(previewFile.value)
  }
}

const renameItem = (row) => {
  renameTarget.value = row
  renameValue.value = row.origin_name || row.name
  showRenameDialog.value = true
}

const doRename = async () => {
  if (!renameValue.value.trim()) return ElMessage.warning('请输入名称')
  try {
    if (renameTarget.value.is_folder) {
      await api.put(`/files/folders/${renameTarget.value.id}`, { name: renameValue.value })
    } else {
      await api.put(`/files/${renameTarget.value.id}/rename`, { name: renameValue.value })
    }
    ElMessage.success('重命名成功')
    showRenameDialog.value = false
    loadFiles()
    loadFolders()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重命名失败')
  }
}

const deleteItem = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除吗？删除后可在回收站恢复', '确认删除', { type: 'warning' })
    if (row.is_folder) await api.delete(`/files/folders/${row.id}`)
    else await api.delete(`/files/${row.id}`)
    ElMessage.success('已移入回收站')
    loadFiles()
    loadFolders()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const batchDelete = async () => {
  const fileIds = selectedItems.value.filter(item => !item.is_folder).map(item => item.id)
  const folderIds = selectedItems.value.filter(item => item.is_folder).map(item => item.id)
  if (!fileIds.length && !folderIds.length) return ElMessage.warning('请选择要删除的文件')
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedItems.value.length} 个项目吗？`, '确认删除', { type: 'warning' })
    for (const folderId of folderIds) await api.delete(`/files/folders/${folderId}`)
    if (fileIds.length) await api.post('/files/batch-delete', { file_ids: fileIds })
    ElMessage.success('已移入回收站')
    loadFiles()
    loadFolders()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const showMoveDialog = (row) => {
  moveCopyMode.value = 'move'
  moveCopyTarget.value = row
  selectedTargetFolder.value = null
  showMoveCopyDialog.value = true
}

const showCopyDialog = (row) => {
  moveCopyMode.value = 'copy'
  moveCopyTarget.value = row
  selectedTargetFolder.value = null
  showMoveCopyDialog.value = true
}

const handleTreeSelect = (data) => {
  selectedTargetFolder.value = data.id
}

const doMoveCopy = async () => {
  try {
    if (moveCopyMode.value === 'move') {
      await api.post(`/files/${moveCopyTarget.value.id}/move`, { target_folder_id: selectedTargetFolder.value })
      ElMessage.success('移动成功')
    } else {
      await api.post(`/files/${moveCopyTarget.value.id}/copy`, { target_folder_id: selectedTargetFolder.value })
      ElMessage.success('复制成功')
    }
    showMoveCopyDialog.value = false
    loadFiles()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const handleSelectionChange = (selection) => {
  selectedItems.value = selection
}

const applyAdvancedSearch = () => {
  showAdvancedSearch.value = false
  loadFiles()
}

const resetAdvancedSearch = () => {
  advancedFilters.value = { keyword: '', ext: '', dateRange: null, sizeRange: '' }
  loadFiles()
}

const loadTrash = async () => {
  trashLoading.value = true
  try {
    const res = await api.get('/files/trash/list', { params: { page_size: 100 } })
    trashFiles.value = res.items || []
  } catch (error) {
    console.error('加载回收站失败:', error)
  } finally {
    trashLoading.value = false
  }
}

const restoreFile = async (file) => {
  try {
    await api.post(`/files/trash/${file.id}/restore`)
    ElMessage.success('文件已恢复')
    loadTrash()
    loadFiles()
  } catch (error) {
    ElMessage.error('恢复失败')
  }
}

const permanentDelete = async (file) => {
  try {
    await ElMessageBox.confirm('彻底删除后无法恢复，确定要删除吗？', '警告', { type: 'warning' })
    await api.delete(`/files/trash/${file.id}`)
    ElMessage.success('已彻底删除')
    loadTrash()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('删除失败')
  }
}

const emptyTrash = async () => {
  try {
    await ElMessageBox.confirm('清空回收站后所有文件将无法恢复，确定要清空吗？', '警告', { type: 'warning' })
    await api.delete('/files/trash')
    ElMessage.success('回收站已清空')
    loadTrash()
  } catch (error) {
    if (error !== 'cancel') ElMessage.error('操作失败')
  }
}

// 监听点击事件关闭右键菜单
const handleClickOutside = () => {
  if (contextMenuVisible.value) hideContextMenu()
}

onMounted(async () => {
  await loadPersonalSpace()
  loadFiles()
  loadFolders()
  fetchServerIp()  // 异步获取服务器 IP
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.files-page {
  background: transparent;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
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

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.file-item {
  display: flex;
  align-items: center;
}

.file-icon-wrapper {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
  flex-shrink: 0;
}

.file-icon-wrapper-lg {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.file-icon {
  font-size: 24px;
  margin-right: 10px;
}

.file-name {
  cursor: pointer;
  transition: color 0.2s;
  color: var(--text-main);
}

.file-name:hover {
  color: var(--primary);
}

.grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.grid-item {
  cursor: pointer;
  transition: all 0.3s ease;
  border-radius: 22px;
  border: 1px solid rgba(218, 229, 247, 0.92);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
}

.grid-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 22px 50px rgba(70, 102, 155, 0.18);
}

.grid-item-selected {
  border: 2px solid var(--primary) !important;
  box-shadow: 0 10px 28px rgba(47, 123, 255, 0.22);
}

.grid-item-content {
  text-align: center;
  padding: 20px;
}

.grid-icon {
  margin-bottom: 16px;
}

.grid-info {
  text-align: left;
}

.grid-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 8px;
}

.grid-meta {
  font-size: 12px;
  color: var(--text-light);
  display: flex;
  justify-content: space-between;
}

.grid-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid rgba(224, 233, 248, 0.75);
  background: rgba(247, 250, 255, 0.6);
  border-radius: 0 0 22px 22px;
}

.grid-item-skeleton {
  height: 220px;
}

.context-menu {
  position: fixed;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 16px;
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.18);
  border: 1px solid rgba(218, 229, 247, 0.92);
  z-index: 9999;
  min-width: 140px;
  padding: 8px 0;
  backdrop-filter: blur(20px);
}

.context-menu-item {
  padding: 10px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text-regular);
  transition: all 0.2s;
  border-radius: 10px;
  margin: 2px 6px;
}

.context-menu-item:hover {
  background: rgba(47, 123, 255, 0.08);
  color: var(--primary);
}

.context-menu-divider {
  height: 1px;
  background: rgba(224, 233, 248, 0.75);
  margin: 6px 12px;
}

.context-menu-danger {
  color: var(--red);
}

.context-menu-danger:hover {
  background: rgba(255, 91, 110, 0.08);
  color: var(--red);
}

.upload-progress {
  margin-top: 12px;
}

.upload-area {
  border: 2px dashed #d9e1ec;
  border-radius: 12px;
  padding: 40px 20px;
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
  margin-bottom: 8px;
}

.upload-area .el-upload__text {
  color: #8c939d;
  font-size: 14px;
}

.upload-area .el-upload__text em {
  color: #5b9aff;
  font-style: normal;
}

.selected-files {
  margin-top: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.selected-file-item {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 6px;
  background: #f5f7fa;
  margin-bottom: 4px;
  font-size: 13px;
}

.selected-file-item .file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selected-file-item .file-size {
  color: #909399;
  margin: 0 8px;
  font-size: 12px;
}

:deep(.el-breadcrumb) {
  font-size: 14px;
}

:deep(.el-breadcrumb__item) {
  cursor: pointer;
}

:deep(.el-breadcrumb__inner) {
  color: var(--text-regular);
  transition: color 0.2s;
}

:deep(.el-breadcrumb__item:hover .el-breadcrumb__inner) {
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
</style>
