<template>
  <div class="groups-page">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>我的群组</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon> 创建群组
          </el-button>
        </div>
      </template>

      <el-table :data="groups" v-loading="loading">
        <el-table-column label="群组名称" prop="name">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
            <el-badge :value="row.unread_count" :hidden="!row.unread_count" :max="99" style="margin-left: 8px" />
          </template>
        </el-table-column>
        <el-table-column label="描述" prop="description" show-overflow-tooltip />
        <el-table-column label="成员数" width="100">
          <template #default="{ row }">{{ row.member_count || 0 }}</template>
        </el-table-column>
        <el-table-column label="我的角色" width="100">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.my_role)" size="small">
              {{ getRoleName(row.my_role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="邀请码" width="150">
          <template #default="{ row }">
            <span v-if="row.invite_code">{{ row.invite_code }}</span>
            <span v-else style="color: #909399">未设置</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openGroup(row)">详情</el-button>
            <el-button size="small" type="primary" @click="openSpace(row)">空间</el-button>
            <el-button size="small" type="danger" @click="leaveGroup(row)" v-if="row.my_role !== 'owner'">
              退出
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建群组对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建群组" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="群组名称" required>
          <el-input v-model="createForm.name" placeholder="请输入群组名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="请输入群组描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createGroup" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 加入群组对话框 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>加入群组</span>
      </template>
      <div style="display: flex; gap: 10px">
        <el-input v-model="joinCode" placeholder="请输入邀请码" style="width: 200px" />
        <el-button type="primary" @click="joinGroup" :loading="joining">加入群组</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import { notificationService } from '@/utils/notifications'

const router = useRouter()

const groups = ref([])
const loading = ref(false)
const showCreateDialog = ref(false)
const creating = ref(false)
const joining = ref(false)
const joinCode = ref('')

const createForm = ref({
  name: '',
  description: ''
})

const getRoleType = (role) => {
  const map = {
    'owner': 'danger',
    'manager': 'warning',
    'member': 'primary',
    'viewer': 'info'
  }
  return map[role] || 'info'
}

const getRoleName = (role) => {
  const map = {
    'owner': '群主',
    'manager': '管理员',
    'member': '成员',
    'viewer': '访客'
  }
  return map[role] || role
}

const loadGroups = async () => {
  loading.value = true
  try {
    groups.value = await api.get('/groups')
    // 添加角色信息
    for (const group of groups.value) {
      const detail = await api.get(`/groups/${group.id}`)
      group.my_role = detail.my_role || 'member'
    }
  } catch (error) {
    console.error('加载群组失败:', error)
    ElMessage.error('加载群组失败')
  } finally {
    loading.value = false
  }
}

const createGroup = async () => {
  if (!createForm.value.name) {
    ElMessage.warning('请输入群组名称')
    return
  }

  creating.value = true
  try {
    await api.post('/groups', createForm.value)
    ElMessage.success('群组创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '' }
    loadGroups()
  } catch (error) {
    ElMessage.error('创建群组失败')
  } finally {
    creating.value = false
  }
}

const joinGroup = async () => {
  if (!joinCode.value) {
    ElMessage.warning('请输入邀请码')
    return
  }

  joining.value = true
  try {
    const result = await api.post(`/groups/join/${joinCode.value}`)
    ElMessage.success(result.message || '加入成功')
    joinCode.value = ''
    loadGroups()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加入失败')
  } finally {
    joining.value = false
  }
}

const openGroup = (group) => {
  router.push(`/groups/${group.id}`)
}

const openSpace = (group) => {
  if (group.space_id) {
    router.push(`/space/${group.space_id}`)
  }
}

const leaveGroup = async (group) => {
  try {
    await ElMessageBox.confirm('确定要退出该群组吗？', '提示', { type: 'warning' })
    await api.post(`/groups/${group.id}/leave`)
    ElMessage.success('已退出群组')
    loadGroups()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('退出失败')
    }
  }
}

onMounted(() => {
  loadGroups()
  // 监听群组消息，实时更新未读数
  notificationService.on('group_chat_message', handleGroupMessage)
  // 监听群组消息已读事件
  window.addEventListener('group-notifications-read', handleNotificationsRead)
})

onUnmounted(() => {
  notificationService.off('group_chat_message', handleGroupMessage)
  window.removeEventListener('group-notifications-read', handleNotificationsRead)
})

// 处理群组消息，实时更新红点
const handleGroupMessage = (data) => {
  const group = groups.value.find(g => g.id === data.group_id)
  if (group) {
    group.unread_count = (group.unread_count || 0) + 1
  }
}

// 处理群组消息已读，清除红点
const handleNotificationsRead = (event) => {
  const { groupId } = event.detail
  const group = groups.value.find(g => g.id === groupId)
  if (group) {
    group.unread_count = 0
  }
}
</script>

<style scoped>
.groups-page {
  max-width: 1200px;
}
</style>
