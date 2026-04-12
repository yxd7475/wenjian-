/**
 * 文件工具函数
 */

// 格式化文件大小
export function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化日期
export function formatDate(dateStr, format = 'datetime') {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  if (format === 'date') {
    return date.toLocaleDateString('zh-CN')
  }
  return date.toLocaleString('zh-CN')
}

// 获取文件图标
export function getFileIcon(ext) {
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
  return iconMap[ext?.toLowerCase()] || 'Document'
}

// 获取文件图标颜色
export function getFileIconColor(ext) {
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
  return colorMap[ext?.toLowerCase()] || '#909399'
}

// 判断是否可预览
export function isPreviewable(ext) {
  const previewable = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'pdf', 'txt', 'md']
  return previewable.includes(ext?.toLowerCase())
}

// 判断是否是图片
export function isImage(ext) {
  const images = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']
  return images.includes(ext?.toLowerCase())
}

// 获取文件扩展名
export function getFileExtension(filename) {
  if (!filename) return ''
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}
