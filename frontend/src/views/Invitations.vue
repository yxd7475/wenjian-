<template>
  <div class="invitations-page">
    <el-tabs v-model="activeTab">
      <!-- 收到的邀请 -->
      <el-tab-pane label="收到的邀请" name="received">
        <el-card>
          <el-table :data="receivedInvitations" v-loading="loadingReceived">
            <el-table-column label="群组" prop="group_name" />
            <el-table-column label="邀请人" prop="inviter_name" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusName(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="过期时间" width="180">
              <template #default="{ row }">{{ formatDate(row.expire_at) }}</template>
            </el-table-column>
            <el-table-column label="邀请时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <el-button-group v-if="row.status === 'pending'">
                  <el-button size="small" type="primary" @click="acceptInvitation(row)">接受</el-button>
                  <el-button size="small" @click="rejectInvitation(row)">拒绝</el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loadingReceived && receivedInvitations.length === 0" description="暂无邀请" />
        </el-card>
      </el-tab-pane>

      <!-- 发出的邀请 -->
      <el-tab-pane label="发出的邀请" name="sent">
        <el-card>
          <el-table :data="sentInvitations" v-loading="loadingSent">
            <el-table-column label="群组" prop="group_name" />
            <el-table-column label="被邀请人">
              <template #default="{ row }">
                {{ row.invitee_name || '通用链接' }}
              </template>
            </el-table-column>
            <el-table-column label="邀请码" prop="invite_code" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusName(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="过期时间" width="180">
              <template #default="{ row }">{{ formatDate(row.expire_at) }}</template>
            </el-table-column>
            <el-table-column label="创建时间" width="180">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loadingSent && sentInvitations.length === 0" description="暂无发出的邀请" />
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const activeTab = ref('received')
const receivedInvitations = ref([])
const sentInvitations = ref([])
const loadingReceived = ref(false)
const loadingSent = ref(false)

const getStatusType = (status) => {
  const map = {
    'pending': 'warning',
    'accepted': 'success',
    'rejected': 'danger',
    'expired': 'info'
  }
  return map[status] || 'info'
}

const getStatusName = (status) => {
  const map = {
    'pending': '待处理',
    'accepted': '已接受',
    'rejected': '已拒绝',
    'expired': '已过期'
  }
  return map[status] || status
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const loadReceivedInvitations = async () => {
  loadingReceived.value = true
  try {
    receivedInvitations.value = await api.get('/invitations')
  } catch (error) {
    console.error('加载邀请失败:', error)
  } finally {
    loadingReceived.value = false
  }
}

const loadSentInvitations = async () => {
  loadingSent.value = true
  try {
    sentInvitations.value = await api.get('/invitations/my-sent')
  } catch (error) {
    console.error('加载发出的邀请失败:', error)
  } finally {
    loadingSent.value = false
  }
}

const acceptInvitation = async (invitation) => {
  try {
    const result = await api.post(`/invitations/${invitation.id}/accept`)
    ElMessage.success(result.message || '已加入群组')
    loadReceivedInvitations()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '接受邀请失败')
  }
}

const rejectInvitation = async (invitation) => {
  try {
    await api.post(`/invitations/${invitation.id}/reject`)
    ElMessage.success('已拒绝邀请')
    loadReceivedInvitations()
  } catch (error) {
    ElMessage.error('拒绝失败')
  }
}

onMounted(() => {
  loadReceivedInvitations()
  loadSentInvitations()
})
</script>

<style scoped>
.invitations-page {
  max-width: 1200px;
}
</style>
