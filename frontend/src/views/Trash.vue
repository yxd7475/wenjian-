<template>
  <div class="trash-page">
    <div class="page-header">
      <h2>回收站</h2>
      <p class="tip">删除的文件会保留在回收站中，可以恢复或彻底删除</p>
    </div>

    <el-table :data="trashFiles" v-loading="loading" empty-text="回收站为空">
      <el-table-column label="名称" prop="origin_name" min-width="200" />
      <el-table-column label="大小" width="120">
        <template #default="{ row }">{{ row.size ? formatSize(row.size) : '-' }}</template>
      </el-table-column>
      <el-table-column label="删除时间" width="180">
        <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" type="primary" @click="restoreFile(row)">恢复</el-button>
            <el-button size="small" type="danger" @click="permanentDelete(row)" v-if="userStore.isAdmin">彻底删除</el-button>
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <div class="trash-footer" v-if="trashFiles.length > 0">
      <el-button v-if="userStore.isAdmin" type="danger" @click="emptyTrash">清空回收站</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const userStore = useUserStore()
const trashFiles = ref([])
const loading = ref(false)

const formatSize = (bytes) => {
  if (!bytes) return '-'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadTrash = async () => {
  loading.value = true
  try {
    const res = await api.get('/files/trash/list', { params: { page_size: 100 } })
    trashFiles.value = res.items || []
  } catch (error) {
    console.error('加载回收站失败:', error)
  } finally {
    loading.value = false
  }
}

const restoreFile = async (file) => {
  try {
    await api.post(`/files/trash/${file.id}/restore`)
    ElMessage.success('文件已恢复')
    loadTrash()
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

onMounted(() => {
  loadTrash()
})
</script>

<style scoped>
.trash-page {
  max-width: 1200px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 800;
  color: #112544;
}

.tip {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.trash-footer {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
