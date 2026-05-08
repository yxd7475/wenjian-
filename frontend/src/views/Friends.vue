<template>
  <div class="friends-page">
    <el-tabs v-model="activeTab">
      <!-- 好友列表 -->
      <el-tab-pane label="好友列表" name="friends">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span>我的好友 ({{ friends.length }})</span>
              <el-button type="primary" size="small" @click="showSearchDialog = true">
                <el-icon><Plus /></el-icon> 添加好友
              </el-button>
            </div>
          </template>

          <el-table :data="friends" v-loading="loadingFriends">
            <el-table-column label="用户名" prop="username" />
            <el-table-column label="姓名" prop="real_name" />
            <el-table-column label="成为好友时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button-group>
                  <el-button size="small" type="primary" @click="openChat(row)">发消息</el-button>
                  <el-button size="small" type="danger" @click="deleteFriend(row)">删除</el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loadingFriends && friends.length === 0" description="暂无好友">
            <el-button type="primary" @click="showSearchDialog = true">添加好友</el-button>
          </el-empty>
        </el-card>
      </el-tab-pane>

      <!-- 收到的申请 -->
      <el-tab-pane label="好友申请" name="requests">
        <el-card>
          <template #header>
            <span>收到的申请 ({{ requests.length }})</span>
          </template>

          <el-table :data="requests" v-loading="loadingRequests">
            <el-table-column label="用户名" prop="username" />
            <el-table-column label="姓名" prop="real_name" />
            <el-table-column label="附言" prop="message">
              <template #default="{ row }">{{ row.message || '-' }}</template>
            </el-table-column>
            <el-table-column label="申请时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button-group>
                  <el-button size="small" type="primary" @click="acceptRequest(row)">接受</el-button>
                  <el-button size="small" @click="rejectRequest(row)">拒绝</el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loadingRequests && requests.length === 0" description="暂无好友申请" />
        </el-card>
      </el-tab-pane>

      <!-- 发出的申请 -->
      <el-tab-pane label="发出的申请" name="sent">
        <el-card>
          <template #header>
            <span>发出的申请 ({{ sentRequests.length }})</span>
          </template>

          <el-table :data="sentRequests" v-loading="loadingSent">
            <el-table-column label="用户名" prop="username" />
            <el-table-column label="姓名" prop="real_name" />
            <el-table-column label="附言" prop="message">
              <template #default="{ row }">{{ row.message || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">待处理</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="申请时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loadingSent && sentRequests.length === 0" description="暂无发出的申请" />
        </el-card>
      </el-tab-pane>

      <!-- 黑名单 -->
      <el-tab-pane label="黑名单" name="blocked">
        <el-card>
          <template #header>
            <span>黑名单 ({{ blockedUsers.length }})</span>
          </template>

          <el-table :data="blockedUsers" v-loading="loadingBlocked">
            <el-table-column label="用户名" prop="username" />
            <el-table-column label="姓名" prop="real_name" />
            <el-table-column label="拉黑时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="unblockUser(row)">解除拉黑</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loadingBlocked && blockedUsers.length === 0" description="黑名单为空" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 搜索用户对话框 -->
    <el-dialog v-model="showSearchDialog" title="添加好友" width="500px">
      <el-input
        v-model="searchKeyword"
        placeholder="输入用户名、姓名或唯一标识码搜索"
        clearable
        @keyup.enter="searchUsers"
        style="margin-bottom: 16px"
      >
        <template #append>
          <el-button @click="searchUsers" :loading="searching">搜索</el-button>
        </template>
      </el-input>

      <div v-if="searchResults.length > 0" class="search-results">
        <div v-for="user in searchResults" :key="user.id" class="search-result-item">
          <div class="user-info">
            <span class="username">{{ user.username }}</span>
            <span class="real-name">{{ user.real_name || '-' }}</span>
            <span class="unique-id">ID: {{ user.unique_id || '-' }}</span>
          </div>
          <div class="user-actions">
            <el-tag v-if="user.is_friend" size="small" type="success">已是好友</el-tag>
            <el-tag v-else-if="user.has_pending_request" size="small" type="warning">申请中</el-tag>
            <el-tag v-else-if="user.has_blocked_me" size="small" type="danger">无法添加</el-tag>
            <el-tag v-else-if="user.is_blocked" size="small" type="info">已拉黑</el-tag>
            <el-button v-else size="small" type="primary" @click="sendRequest(user)">添加好友</el-button>
          </div>
        </div>
      </div>

      <el-empty v-else-if="searchKeyword && !searching" description="输入关键词搜索用户" />
    </el-dialog>

    <!-- 发送好友申请对话框 -->
    <el-dialog v-model="showRequestDialog" title="发送好友申请" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">
          <span>{{ selectedUser?.username }} ({{ selectedUser?.real_name || '-' }})</span>
        </el-form-item>
        <el-form-item label="附言">
          <el-input
            v-model="requestMessage"
            type="textarea"
            :rows="3"
            placeholder="打个招呼吧（选填）"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRequestDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmSendRequest" :loading="sending">发送申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'

const router = useRouter()
const activeTab = ref('friends')

// 数据
const friends = ref([])
const requests = ref([])
const sentRequests = ref([])
const blockedUsers = ref([])

// 加载状态
const loadingFriends = ref(false)
const loadingRequests = ref(false)
const loadingSent = ref(false)
const loadingBlocked = ref(false)

// 搜索相关
const showSearchDialog = ref(false)
const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)

// 发送申请
const showRequestDialog = ref(false)
const selectedUser = ref(null)
const requestMessage = ref('')
const sending = ref(false)

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 加载好友列表
const loadFriends = async () => {
  loadingFriends.value = true
  try {
    friends.value = await api.get('/friends')
  } catch (error) {
    console.error('加载好友失败:', error)
  } finally {
    loadingFriends.value = false
  }
}

// 加载收到的申请
const loadRequests = async () => {
  loadingRequests.value = true
  try {
    requests.value = await api.get('/friends/requests')
  } catch (error) {
    console.error('加载申请失败:', error)
  } finally {
    loadingRequests.value = false
  }
}

// 加载发出的申请
const loadSentRequests = async () => {
  loadingSent.value = true
  try {
    sentRequests.value = await api.get('/friends/sent')
  } catch (error) {
    console.error('加载发出的申请失败:', error)
  } finally {
    loadingSent.value = false
  }
}

// 加载黑名单
const loadBlocked = async () => {
  loadingBlocked.value = true
  try {
    blockedUsers.value = await api.get('/friends/blocked')
  } catch (error) {
    console.error('加载黑名单失败:', error)
  } finally {
    loadingBlocked.value = false
  }
}

// 搜索用户
const searchUsers = async () => {
  if (!searchKeyword.value.trim()) return
  searching.value = true
  try {
    searchResults.value = await api.get('/friends/search', { params: { keyword: searchKeyword.value } })
  } catch (error) {
    ElMessage.error('搜索失败')
  } finally {
    searching.value = false
  }
}

// 发送好友申请
const sendRequest = (user) => {
  selectedUser.value = user
  requestMessage.value = ''
  showRequestDialog.value = true
}

const confirmSendRequest = async () => {
  sending.value = true
  try {
    await api.post('/friends/request', {
      user_id: selectedUser.value.id,
      message: requestMessage.value
    })
    ElMessage.success('好友申请已发送')
    showRequestDialog.value = false
    showSearchDialog.value = false
    searchResults.value = []
    searchKeyword.value = ''
    loadSentRequests()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '发送失败')
  } finally {
    sending.value = false
  }
}

// 接受申请
const acceptRequest = async (request) => {
  try {
    await api.post(`/friends/${request.id}/accept`)
    ElMessage.success('已成为好友')
    loadRequests()
    loadFriends()
  } catch (error) {
    ElMessage.error('接受失败')
  }
}

// 拒绝申请
const rejectRequest = async (request) => {
  try {
    await api.post(`/friends/${request.id}/reject`)
    ElMessage.success('已拒绝')
    loadRequests()
  } catch (error) {
    ElMessage.error('拒绝失败')
  }
}

// 打开聊天
const openChat = (friend) => {
  router.push({ path: '/chat', query: { friendId: friend.friend_id } })
}

// 删除好友
const deleteFriend = async (friend) => {
  try {
    await ElMessageBox.confirm(`确定要删除好友 "${friend.username}" 吗？`, '确认', { type: 'warning' })
    await api.delete(`/friends/${friend.id}`)
    ElMessage.success('已删除好友')
    loadFriends()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 解除拉黑
const unblockUser = async (user) => {
  try {
    await api.delete(`/friends/${user.user_id}/block`)
    ElMessage.success('已解除拉黑')
    loadBlocked()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

onMounted(() => {
  loadFriends()
  loadRequests()
  loadSentRequests()
  loadBlocked()
})
</script>

<style scoped>
.friends-page {
  max-width: 1200px;
}

.search-results {
  max-height: 300px;
  overflow-y: auto;
}

.search-result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  transition: background 0.2s;
}

.search-result-item:last-child {
  border-bottom: none;
}

.search-result-item:hover {
  background: rgba(47, 123, 255, 0.06);
  border-radius: 13px;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.username {
  font-weight: 700;
  color: var(--text-main);
}

.real-name {
  font-size: 12px;
  color: var(--text-light);
}

.unique-id {
  font-size: 11px;
  color: #b0bdd0;
  font-family: monospace;
}

:deep(.el-card) {
  border-radius: 22px;
  border: 1px solid rgba(218, 229, 247, 0.92);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  box-shadow: 0 18px 45px rgba(70, 102, 155, 0.12);
}

:deep(.el-card__header) {
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
  font-weight: 800;
  color: var(--text-main);
}

:deep(.el-table) {
  border-radius: 16px;
  overflow: hidden;
}

:deep(.el-table th.el-table__cell) {
  background: rgba(247, 250, 255, 0.9) !important;
  color: #6c7c95;
  font-weight: 700;
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid rgba(229, 237, 250, 0.8);
}

:deep(.el-table__row:hover > td) {
  background: rgba(47, 123, 255, 0.035) !important;
}

:deep(.el-dialog) {
  border-radius: 22px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(224, 233, 248, 0.75);
}

:deep(.el-dialog__title) {
  font-weight: 800;
  color: var(--text-main);
}

:deep(.el-dialog__footer) {
  border-top: 1px solid rgba(224, 233, 248, 0.75);
}
</style>
