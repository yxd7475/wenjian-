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
        <el-button @click="showTrashDialog = true">
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
              <el-icon class="file-icon" :style="{ color: getFileIconColor(row) }">
                <component :is="getFileIcon(row)" />
              </el-icon>
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
            <el-icon :size="48" :style="{ color: getFileIconColor(file) }">
              <component :is="getFileIcon(file)" />
            </el-icon>
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
    <el-dialog v-model="showUploadDialog" title="上传文件" width="600px">
      <el-upload
        ref="uploadRef"
        :action="uploadUrl"
        :headers="uploadHeaders"
        :data="uploadData"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :on-progress="handleUploadProgress"
        :before-upload="beforeUpload"
        multiple
        drag
        :auto-upload="false"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持常见文件格式</div>
          <div v-if="uploadProgress > 0" class="upload-progress">
            <el-progress :percentage="uploadProgress" :status="uploadStatus" />
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="submitUpload" :loading="uploading">
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

    <!-- 文件预览对话框 -->
    <el-dialog v-model="showPreviewDialog" :title="previewFile?.origin_name" width="80%" top="5vh">
      <div v-if="previewFileType === 'image'" style="text-align: center">
        <img :src="previewUrl" style="max-width: 100%; max-height: 70vh" />
      </div>
      <iframe
        v-else-if="previewFileType === 'pdf'"
        :src="previewUrl"
        style="width: 100%; height: 75vh; border: none"
      />
      <video
        v-else-if="previewFileType === 'video'"
        :src="previewUrl"
        controls
        style="max-width: 100%; max-height: 75vh"
      />
      <audio
        v-else-if="previewFileType === 'audio'"
        :src="previewUrl"
        controls
        style="width: 100%"
      />
      <pre v-else-if="previewFileType === 'text'" class="text-preview">{{ textContent }}</pre>
      <div v-else style="text-align: center; padding: 40px; color: #909399">
        该文件类型不支持预览，请下载后查看
      </div>
    </el-dialog>

    <!-- 回收站对话框 -->
    <el-dialog v-model="showTrashDialog" title="回收站" width="900px">
      <el-table :data="trashFiles" v-loading="trashLoading">
        <el-table-column label="名称" prop="origin_name" min-width="200" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ row.size ? formatSize(row.size) : '-' }}</template>
        </el-table-column>
        <el-table-column label="删除时间" width="160">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="restoreFile(row)">恢复</el-button>
            <el-button size="small" type="danger" @click="permanentDelete(row)" v-if="userStore.isAdmin">彻底删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button v-if="userStore.isAdmin" type="danger" @click="emptyTrash">清空回收站</el-button>
        <el-button @click="showTrashDialog = false">关闭</el-button>
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
          <el-input :value="shareLink" readonly>
            <template #append>
              <el-button @click="copyShareLink">复制</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="服务器地址" v-if="isLocalhost">
          <el-input v-model="serverIp" placeholder="输入局域网IP，如 10.18.53.55">
            <template #append>
              <el-button @click="saveServerIp">保存</el-button>
            </template>
          </el-input>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            局域网分享时需配置此电脑的IP地址
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
  Folder, Document, Picture, VideoCamera, Headset, Files, Notebook,
  ArrowUp, ArrowDown, Share
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'

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
const previewFileType = ref('')
const textContent = ref('')

// 移动/复制相关
const moveCopyMode = ref('move')
const moveCopyTarget = ref(null)
const selectedTargetFolder = ref(null)

// 上传相关
const uploadRef = ref(null)
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

const shareLink = computed(() => {
  if (!shareResult.value) return ''
  // 如果是localhost访问，尝试使用局域网IP
  let baseUrl = window.location.origin
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    // 尝试从localStorage获取配置的IP
    const configIp = localStorage.getItem('server_ip')
    if (configIp) {
      baseUrl = `${window.location.protocol}//${configIp}:${window.location.port}`
    }
  }
  return `${baseUrl}/share/${shareResult.value.share_code}`
})

// 上传配置
const uploadUrl = computed(() => '/api/files/upload')
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}))
const uploadData = computed(() => {
  const data = {}
  if (currentFolderId.value) data.folder_id = currentFolderId.value
  if (personalSpaceId.value) data.space_id = personalSpaceId.value
  return data
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
const canPreview = (row) => {
  if (!row || row.is_folder) return false
  const ext = row.ext?.toLowerCase()
  const previewExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'pdf', 'txt', 'md', 'log', 'json', 'xml', 'mp4', 'webm', 'mp3', 'wav']
  return previewExts.includes(ext)
}

const toggleSortOrder = () => {
  sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
}

const getFileIcon = (row) => {
  if (row.is_folder) return Folder
  const ext = row.ext?.toLowerCase()
  const extIconMap = {
    'pdf': Document, 'doc': Document, 'docx': Document, 'xls': Document, 'xlsx': Document,
    'ppt': Document, 'pptx': Document, 'jpg': Picture, 'jpeg': Picture, 'png': Picture,
    'gif': Picture, 'webp': Picture, 'bmp': Picture, 'mp3': Headset, 'wav': Headset,
    'mp4': VideoCamera, 'avi': VideoCamera, 'mov': VideoCamera, 'webm': VideoCamera,
    'zip': Files, 'rar': Files, '7z': Files, 'txt': Notebook, 'md': Notebook, 'log': Notebook
  }
  return extIconMap[ext] || Document
}

const getFileIconColor = (row) => {
  if (row.is_folder) return '#E6A23C'
  const ext = row.ext?.toLowerCase()
  const colorMap = {
    'pdf': '#F56C6C', 'doc': '#409EFF', 'docx': '#409EFF', 'xls': '#67C23A', 'xlsx': '#67C23A',
    'ppt': '#E6A23C', 'pptx': '#E6A23C', 'jpg': '#67C23A', 'jpeg': '#67C23A', 'png': '#67C23A',
    'gif': '#67C23A', 'mp3': '#909399', 'mp4': '#909399', 'txt': '#909399', 'md': '#909399'
  }
  return colorMap[ext] || '#909399'
}

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
    showShareDialog.value = false
    showShareResult.value = true
  } catch (error) {
    ElMessage.error('创建分享失败')
  } finally {
    shareCreating.value = false
  }
}

const copyShareLink = () => {
  navigator.clipboard.writeText(shareLink.value)
  ElMessage.success('链接已复制到剪贴板')
}

// 局域网IP配置
const isLocalhost = computed(() => {
  return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
})
const serverIp = ref(localStorage.getItem('server_ip') || '')
const saveServerIp = () => {
  if (serverIp.value) {
    localStorage.setItem('server_ip', serverIp.value)
    ElMessage.success('服务器地址已保存')
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
  // 本地系统不限制文件大小
  return true
}

const handleUploadProgress = (event) => {
  uploadProgress.value = Math.round(event.percent)
  uploadStatus.value = uploadProgress.value >= 100 ? 'success' : ''
}

const submitUpload = () => {
  uploading.value = true
  uploadProgress.value = 0
  uploadStatus.value = ''
  uploadRef.value.submit()
}

const handleUploadSuccess = () => {
  uploading.value = false
  uploadProgress.value = 100
  uploadStatus.value = 'success'
  ElMessage.success('上传成功')
  showUploadDialog.value = false
  loadFiles()
}

const handleUploadError = () => {
  uploading.value = false
  uploadStatus.value = 'exception'
  ElMessage.error('上传失败')
}

const downloadFile = async (file) => {
  try {
    const response = await fetch(`/api/files/${file.id}/download`, {
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
    const response = await fetch('/api/files/batch-download', {
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
  const token = localStorage.getItem('token')
  previewUrl.value = `/api/files/${file.id}/preview?token=${token}`
  const ext = file.ext?.toLowerCase()
  if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext)) {
    previewFileType.value = 'image'
  } else if (ext === 'pdf') {
    previewFileType.value = 'pdf'
  } else if (['mp4', 'webm', 'mov'].includes(ext)) {
    previewFileType.value = 'video'
  } else if (['mp3', 'wav', 'ogg'].includes(ext)) {
    previewFileType.value = 'audio'
  } else if (['txt', 'md', 'log', 'json', 'xml', 'html', 'css', 'js'].includes(ext)) {
    previewFileType.value = 'text'
    try {
      textContent.value = await (await fetch(previewUrl.value)).text()
    } catch {
      textContent.value = '无法读取文件内容'
    }
  } else {
    previewFileType.value = 'unsupported'
  }
  showPreviewDialog.value = true
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
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-left, .toolbar-right {
  display: flex;
  gap: 8px;
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

/* 卡片视图 */
.grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}
.grid-item {
  cursor: pointer;
  transition: all 0.3s;
}
.grid-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.grid-item-selected {
  border: 2px solid #409EFF;
}
.grid-item-content {
  text-align: center;
  padding: 16px;
}
.grid-icon {
  margin-bottom: 12px;
}
.grid-info {
  text-align: left;
}
.grid-name {
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}
.grid-meta {
  font-size: 12px;
  color: #909399;
  display: flex;
  justify-content: space-between;
}
.grid-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 8px;
  border-top: 1px solid #eee;
}
.grid-item-skeleton {
  height: 200px;
}

/* 右键菜单 */
.context-menu {
  position: fixed;
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  min-width: 120px;
  padding: 4px 0;
}
.context-menu-item {
  padding: 8px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}
.context-menu-item:hover {
  background: #f5f7fa;
}
.context-menu-divider {
  height: 1px;
  background: #eee;
  margin: 4px 0;
}
.context-menu-danger {
  color: #F56C6C;
}

/* 文本预览 */
.text-preview {
  max-height: 70vh;
  overflow: auto;
  background: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
}

.upload-progress {
  margin-top: 10px;
}
</style>
