/**
 * WebSocket 通知服务
 */

class NotificationService {
  constructor() {
    this.ws = null
    this.reconnectTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.listeners = new Map()
    this.audioContext = null
    this.notificationPermission = 'default'
    this.soundEnabled = true
    this.desktopEnabled = true
  }

  /**
   * 初始化通知权限
   */
  async initPermissions() {
    // 请求浏览器通知权限
    if ('Notification' in window) {
      this.notificationPermission = Notification.permission
      if (Notification.permission === 'default') {
        this.notificationPermission = await Notification.requestPermission()
      }
    }

    // 初始化音频上下文
    if ('AudioContext' in window || 'webkitAudioContext' in window) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
    }
  }

  /**
   * 播放通知声音
   */
  playNotificationSound(type = 'default') {
    if (!this.soundEnabled || !this.audioContext) return

    try {
      // 恢复音频上下文（需要用户交互后才能播放）
      if (this.audioContext.state === 'suspended') {
        this.audioContext.resume()
      }

      const oscillator = this.audioContext.createOscillator()
      const gainNode = this.audioContext.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(this.audioContext.destination)

      // 根据类型设置不同的音调
      const frequencies = {
        'default': 800,
        'message': 600,
        'warning': 500,
        'success': 700,
        'error': 400
      }

      oscillator.frequency.value = frequencies[type] || frequencies.default
      oscillator.type = 'sine'

      gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.3)

      oscillator.start(this.audioContext.currentTime)
      oscillator.stop(this.audioContext.currentTime + 0.3)
    } catch (e) {
      console.warn('播放通知声音失败:', e)
    }
  }

  /**
   * 发送桌面通知
   */
  showDesktopNotification(title, options = {}) {
    if (!this.desktopEnabled || this.notificationPermission !== 'granted') return

    try {
      const notification = new Notification(title, {
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        requireInteraction: false,
        ...options
      })

      notification.onclick = () => {
        window.focus()
        notification.close()
        if (options.onClick) options.onClick()
      }

      // 3秒后自动关闭
      setTimeout(() => notification.close(), 3000)
    } catch (e) {
      console.warn('桌面通知发送失败:', e)
    }
  }

  /**
   * 设置声音开关
   */
  setSoundEnabled(enabled) {
    this.soundEnabled = enabled
  }

  /**
   * 设置桌面通知开关
   */
  setDesktopEnabled(enabled) {
    this.desktopEnabled = enabled
  }

  /**
   * 连接 WebSocket
   */
  async connect(token) {
    // 初始化通知权限
    await this.initPermissions()

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/${token}`

    try {
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('WebSocket 已连接')
        this.reconnectAttempts = 0
        // 启动心跳
        this.startHeartbeat()
      }

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.handleMessage(message)
        } catch (e) {
          console.error('解析消息失败:', e)
        }
      }

      this.ws.onclose = () => {
        console.log('WebSocket 已断开')
        this.stopHeartbeat()
        this.attemptReconnect(token)
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket 错误:', error)
      }
    } catch (error) {
      console.error('WebSocket 连接失败:', error)
      this.attemptReconnect(token)
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * 尝试重连
   */
  attemptReconnect(token) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('达到最大重连次数，停止重连')
      return
    }

    this.reconnectAttempts++
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000)

    console.log(`${delay / 1000}秒后尝试第 ${this.reconnectAttempts} 次重连`)

    this.reconnectTimer = setTimeout(() => {
      this.connect(token)
    }, delay)
  }

  /**
   * 启动心跳
   */
  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 30000)
  }

  /**
   * 停止心跳
   */
  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  /**
   * 处理消息
   */
  handleMessage(message) {
    const { type, data } = message

    // 通知所有监听器
    if (this.listeners.has(type)) {
      this.listeners.get(type).forEach(callback => callback(data))
    }

    // 通知通用监听器
    if (this.listeners.has('*')) {
      this.listeners.get('*').forEach(callback => callback(message))
    }

    // 根据消息类型播放声音和发送桌面通知
    this.handleNotificationEffects(type, data)
  }

  /**
   * 处理通知效果（声音和桌面通知）
   */
  handleNotificationEffects(type, data) {
    const notificationConfig = {
      'chat_message': {
        sound: 'message',
        title: `新消息`,
        body: data?.content ? `${data.sender_name}: ${data.content.substring(0, 50)}${data.content.length > 50 ? '...' : ''}` : '您收到一条新消息'
      },
      'group_chat_message': {
        sound: 'message',
        title: `群组消息`,
        body: data?.content ? `[${data.group_name}] ${data.sender_name}: ${data.content.substring(0, 50)}${data.content.length > 50 ? '...' : ''}` : '您收到一条群组消息'
      },
      'friend_request': {
        sound: 'default',
        title: '好友申请',
        body: `${data?.username || '有人'} 向你发送了好友申请`
      },
      'friend_accepted': {
        sound: 'success',
        title: '好友申请已接受',
        body: `${data?.username || '对方'} 已接受你的好友申请`
      },
      'group_invite': {
        sound: 'default',
        title: '群组邀请',
        body: `${data?.inviter_name || '有人'} 邀请您加入群组「${data?.group_name || ''}」`
      },
      'group_invite_accepted': {
        sound: 'success',
        title: '邀请已接受',
        body: `${data?.user_name || '对方'} 已接受您的群组邀请`
      },
      'group_invite_rejected': {
        sound: 'warning',
        title: '邀请被拒绝',
        body: `${data?.user_name || '对方'} 拒绝了您的群组邀请`
      },
      'group_joined': {
        sound: 'success',
        title: '已加入群组',
        body: `您已加入群组「${data?.group_name || ''}」`
      },
      'group_removed': {
        sound: 'warning',
        title: '被移出群组',
        body: `您已被移出群组「${data?.group_name || ''}」`
      },
      'invitation': {
        sound: 'default',
        title: '群组邀请',
        body: '您收到了加入群组的邀请'
      },
      'invitation_accepted': {
        sound: 'success',
        title: '邀请已接受',
        body: `${data?.new_member_name || '对方'} 已接受您的邀请`
      },
      'group_member_joined': {
        sound: 'success',
        title: '新成员加入',
        body: `${data?.member?.real_name || data?.member?.username || '新成员'} 加入了群组`
      },
      'new_file': {
        sound: 'default',
        title: '新文件上传',
        body: data?.file?.name ? `${data.file.uploader || '有人'} 上传了 ${data.file.name}` : '群组中有新文件上传'
      },
      'file_deleted': {
        sound: 'warning',
        title: '文件已删除',
        body: '群组中有文件被删除'
      },
      'group_dissolved': {
        sound: 'error',
        title: '群组已解散',
        body: '您所在的群组已被解散'
      },
      'alert': {
        sound: 'warning',
        title: '系统告警',
        body: data?.title || '您收到了一条系统告警'
      },
      'notification': {
        sound: 'default',
        title: '系统通知',
        body: data?.message || '您收到了一条新通知'
      }
    }

    const config = notificationConfig[type]
    if (config) {
      // 播放声音
      this.playNotificationSound(config.sound)

      // 发送桌面通知
      this.showDesktopNotification(config.title, { body: config.body })
    }
  }

  /**
   * 添加消息监听
   */
  on(type, callback) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, [])
    }
    this.listeners.get(type).push(callback)
  }

  /**
   * 移除消息监听
   */
  off(type, callback) {
    if (!this.listeners.has(type)) return
    if (callback) {
      const callbacks = this.listeners.get(type)
      const index = callbacks.indexOf(callback)
      if (index > -1) {
        callbacks.splice(index, 1)
      }
    } else {
      this.listeners.delete(type)
    }
  }
}

// 单例导出
export const notificationService = new NotificationService()

export default notificationService
