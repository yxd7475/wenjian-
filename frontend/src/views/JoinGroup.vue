<template>
  <div class="join-group-page">
    <el-card class="join-card" v-loading="loading">
      <template #header>
        <h2>加入群组</h2>
      </template>

      <div v-if="error" class="error-section">
        <el-result
          icon="error"
          :title="error"
        >
          <template #extra>
            <el-button type="primary" @click="goHome">返回首页</el-button>
          </template>
        </el-result>
      </div>

      <div v-else-if="groupInfo" class="group-info-section">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="群组名称">
            <strong>{{ groupInfo.name }}</strong>
          </el-descriptions-item>
          <el-descriptions-item label="群组描述">
            {{ groupInfo.description || '暂无描述' }}
          </el-descriptions-item>
          <el-descriptions-item label="群主">
            {{ groupInfo.owner_name }}
          </el-descriptions-item>
          <el-descriptions-item label="成员数">
            {{ groupInfo.member_count || 0 }} 人
          </el-descriptions-item>
        </el-descriptions>

        <div class="action-buttons">
          <el-button type="primary" size="large" @click="joinGroup" :loading="joining">
            加入群组
          </el-button>
          <el-button size="large" @click="goHome">
            取消
          </el-button>
        </div>
      </div>

      <div v-else class="loading-section">
        <el-empty description="正在加载群组信息..." />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import api from '@/utils/api'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const loading = ref(true)
const joining = ref(false)
const groupInfo = ref(null)
const error = ref('')
const inviteCode = ref('')

const loadGroupInfo = async () => {
  loading.value = true
  error.value = ''

  try {
    // 获取群组信息
    const result = await api.get(`/groups/info/${inviteCode.value}`)
    groupInfo.value = result
  } catch (err) {
    if (err.response?.status === 404) {
      error.value = '无效的邀请链接'
    } else {
      error.value = err.response?.data?.detail || '加载失败'
    }
  } finally {
    loading.value = false
  }
}

const joinGroup = async () => {
  joining.value = true
  try {
    await api.post(`/groups/join/${inviteCode.value}`)
    ElMessage.success('成功加入群组')
    router.push('/groups')
  } catch (err) {
    if (err.response?.status === 400) {
      ElMessage.warning(err.response?.data?.detail || '您已经是群组成员')
      router.push('/groups')
    } else {
      ElMessage.error(err.response?.data?.detail || '加入失败')
    }
  } finally {
    joining.value = false
  }
}

const goHome = () => {
  router.push('/')
}

onMounted(() => {
  inviteCode.value = route.params.code
  if (!inviteCode.value) {
    error.value = '无效的邀请链接'
    loading.value = false
    return
  }

  // 检查登录状态
  if (!userStore.isLoggedIn) {
    // 保存当前URL，登录后跳回来
    localStorage.setItem('redirectAfterLogin', window.location.pathname)
    ElMessage.warning('请先登录')
    router.push('/login')
    return
  }

  loadGroupInfo()
})
</script>

<style scoped>
.join-group-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.join-card {
  width: 500px;
}

.join-card h2 {
  text-align: center;
  margin: 0;
  color: #303133;
}

.group-info-section {
  margin-top: 20px;
}

.action-buttons {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  gap: 16px;
}

.error-section {
  padding: 20px 0;
}

.loading-section {
  padding: 40px 0;
}
</style>
