/**
 * 文件工具函数
 */

const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']
const videoExts = ['mp4', 'webm', 'mov', 'avi', 'mkv']
const audioExts = ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac']
const textExts = [
  'txt', 'md', 'log', 'json', 'xml', 'html', 'htm', 'css', 'js', 'ts',
  'jsx', 'tsx', 'vue', 'java', 'py', 'sql', 'yaml', 'yml', 'csv', 'ini',
  'conf', 'sh', 'bat', 'ps1'
]
const officeExts = ['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']
const archiveExts = ['zip', 'rar', '7z', 'tar', 'gz']

function resolveExt(input) {
  if (!input) return ''
  if (typeof input === 'string') {
    const parts = input.split('.')
    return parts.length > 1 ? parts.pop().toLowerCase() : ''
  }
  // 优先使用后端返回的 ext 字段
  if (input.ext) return input.ext.toLowerCase()
  const filename = input.origin_name || input.name || input.file_name || ''
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

export function formatSize(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export function formatDate(dateStr, format = 'datetime') {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  if (format === 'date') {
    return date.toLocaleDateString('zh-CN')
  }
  return date.toLocaleString('zh-CN')
}

export function getFileIcon(input) {
  const ext = resolveExt(input)
  if (imageExts.includes(ext)) return 'Picture'
  if (videoExts.includes(ext)) return 'VideoPlay'
  if (audioExts.includes(ext)) return 'Headset'
  if (textExts.includes(ext)) return 'Notebook'
  if (archiveExts.includes(ext)) return 'Files'
  if (['doc', 'docx'].includes(ext)) return 'Document'
  if (['xls', 'xlsx'].includes(ext)) return 'Grid'
  if (['ppt', 'pptx'].includes(ext)) return 'DataBoard'
  if (ext === 'pdf') return 'Reading'
  return 'Document'
}

export function getFileIconColor(input) {
  return '#fff'
}

export function getFileIconBg(input) {
  const ext = resolveExt(input)
  if (imageExts.includes(ext)) return 'linear-gradient(135deg, #a855f7, #7c3aed)'
  if (videoExts.includes(ext)) return 'linear-gradient(135deg, #f97316, #ea580c)'
  if (audioExts.includes(ext)) return 'linear-gradient(135deg, #8b5cf6, #6d28d9)'
  if (textExts.includes(ext)) return 'linear-gradient(135deg, #60a5fa, #3b82f6)'
  if (archiveExts.includes(ext)) return 'linear-gradient(135deg, #fbbf24, #d97706)'
  if (['doc', 'docx'].includes(ext)) return 'linear-gradient(135deg, #3b82f6, #2563eb)'
  if (['xls', 'xlsx'].includes(ext)) return 'linear-gradient(135deg, #22c55e, #16a34a)'
  if (['ppt', 'pptx'].includes(ext)) return 'linear-gradient(135deg, #f97316, #ea580c)'
  if (ext === 'pdf') return 'linear-gradient(135deg, #ef4444, #dc2626)'
  return 'linear-gradient(135deg, #94a3b8, #64748b)'
}

export function getFileIconBgFolder() {
  return 'linear-gradient(135deg, #3b82f6, #2563eb)'
}

export function getFileExtension(filename) {
  if (!filename) return ''
  const parts = filename.split('.')
  return parts.length > 1 ? parts.pop().toLowerCase() : ''
}

export function getPreviewType(input) {
  const ext = resolveExt(input)
  if (imageExts.includes(ext)) return 'image'
  if (ext === 'pdf') return 'pdf'
  if (videoExts.includes(ext)) return 'video'
  if (audioExts.includes(ext)) return 'audio'
  if (textExts.includes(ext)) return 'text'
  if (['doc', 'docx'].includes(ext)) return 'word'
  if (['xls', 'xlsx'].includes(ext)) return 'excel'
  if (['ppt', 'pptx'].includes(ext)) return 'ppt'
  return 'unsupported'
}

export function isPreviewable(input) {
  return getPreviewType(input) !== 'unsupported'
}

export function isImage(input) {
  return imageExts.includes(resolveExt(input))
}

export function isTextPreviewable(input) {
  return getPreviewType(input) === 'text'
}

export function isOfficeDocument(input) {
  return officeExts.includes(resolveExt(input))
}

export function buildFilePreviewUrl(fileId, token = localStorage.getItem('token')) {
  return `/files/api/files/${fileId}/preview?token=${encodeURIComponent(token || '')}`
}

export function buildFileDownloadUrl(fileId, token = localStorage.getItem('token')) {
  return `/files/api/files/${fileId}/download?token=${encodeURIComponent(token || '')}`
}
