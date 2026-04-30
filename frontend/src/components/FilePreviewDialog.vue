<template>
  <el-dialog
    :model-value="modelValue"
    :title="fileName"
    width="80%"
    top="5vh"
    destroy-on-close
    @close="emit('update:modelValue', false)"
  >
    <div v-if="previewType === 'image'" class="image-preview">
      <img :src="previewUrl" :alt="fileName" />
    </div>

    <iframe
      v-else-if="previewType === 'pdf'"
      :src="previewUrl"
      class="pdf-preview"
    />

    <video
      v-else-if="previewType === 'video'"
      :src="previewUrl"
      controls
      class="media-preview"
    />

    <audio
      v-else-if="previewType === 'audio'"
      :src="previewUrl"
      controls
      class="audio-preview"
    />

    <div v-else-if="previewType === 'text'" class="text-preview-wrapper">
      <el-alert
        v-if="textTooLarge"
        type="warning"
        :closable="false"
        title="该文本文件较大，已禁用在线预览，请直接下载查看。"
        show-icon
      />
      <el-skeleton v-else-if="textLoading" :rows="10" animated />
      <el-alert
        v-else-if="textError"
        type="error"
        :closable="false"
        :title="textError"
        show-icon
      />
      <pre v-else class="text-preview">{{ textContent }}</pre>
    </div>

    <div v-else-if="previewType === 'word'" class="office-preview-wrapper">
      <el-skeleton v-if="officeLoading" :rows="10" animated />
      <el-alert
        v-else-if="officeError"
        type="error"
        :closable="false"
        :title="officeError"
        show-icon
      />
      <div v-else class="word-preview" v-html="wordContent"></div>
    </div>

    <div v-else-if="previewType === 'excel'" class="office-preview-wrapper">
      <el-skeleton v-if="officeLoading" :rows="10" animated />
      <el-alert
        v-else-if="officeError"
        type="error"
        :closable="false"
        :title="officeError"
        show-icon
      />
      <div v-else class="excel-preview">
        <el-table :data="excelData" border stripe max-height="65vh" size="small">
          <el-table-column
            v-for="(col, index) in excelColumns"
            :key="index"
            :prop="col"
            :label="col"
            min-width="120"
          />
        </el-table>
        <div v-if="excelSheets.length > 1" class="sheet-tabs">
          <span>工作表：</span>
          <el-tag
            v-for="sheet in excelSheets"
            :key="sheet.name"
            :type="currentSheet === sheet.name ? 'primary' : 'info'"
            @click="switchSheet(sheet.name)"
            style="cursor: pointer; margin-right: 8px"
          >
            {{ sheet.name }}
          </el-tag>
        </div>
      </div>
    </div>

    <div v-else-if="previewType === 'ppt'" class="office-preview-wrapper">
      <el-alert
        type="info"
        :closable="false"
        show-icon
      >
        <template #title>
          <span>PPT 文档暂不支持在线预览，请下载后查看。</span>
        </template>
      </el-alert>
      <div class="ppt-actions">
        <el-button type="primary" @click="emit('download')">下载文件</el-button>
      </div>
    </div>

    <div v-else class="unsupported-preview">
      <el-icon :size="42" color="#909399"><Document /></el-icon>
      <p>当前文件类型暂不支持浏览器内预览。</p>
      <el-button v-if="showDownload" type="primary" @click="emit('download')">下载文件</el-button>
    </div>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Document } from '@element-plus/icons-vue'
import { getPreviewType } from '@/utils/file'
import * as XLSX from 'xlsx'
import mammoth from 'mammoth'
import jschardet from 'jschardet'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  file: {
    type: Object,
    default: null
  },
  previewUrl: {
    type: String,
    default: ''
  },
  textRequest: {
    type: Function,
    default: null
  },
  maxTextPreviewSize: {
    type: Number,
    default: 2 * 1024 * 1024
  },
  showDownload: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'download'])

const textLoading = ref(false)
const textContent = ref('')
const textError = ref('')

const officeLoading = ref(false)
const officeError = ref('')
const wordContent = ref('')
const excelData = ref([])
const excelColumns = ref([])
const excelSheets = ref([])
const currentSheet = ref('')
const excelWorkbook = ref(null)

const fileName = computed(() => props.file?.origin_name || props.file?.name || '文件预览')
const previewType = computed(() => getPreviewType(props.file))
const textTooLarge = computed(() => {
  if (previewType.value !== 'text') return false
  return Number(props.file?.size || 0) > props.maxTextPreviewSize
})

const loadTextPreview = async () => {
  console.log('[loadTextPreview] 开始执行, previewType:', previewType.value, 'modelValue:', props.modelValue)
  textContent.value = ''
  textError.value = ''

  if (!props.modelValue || previewType.value !== 'text' || textTooLarge.value) return

  textLoading.value = true
  try {
    console.log('[loadTextPreview] textRequest:', !!props.textRequest, 'previewUrl:', !!props.previewUrl)
    if (props.textRequest) {
      console.log('[loadTextPreview] 使用 textRequest')
      textContent.value = await props.textRequest()
    } else if (props.previewUrl) {
      console.log('[loadTextPreview] 使用 previewUrl, 开始fetch')
      const response = await fetch(props.previewUrl)
      if (!response.ok) {
        throw new Error('读取文件内容失败')
      }
      const arrayBuffer = await response.arrayBuffer()
      const uint8Array = new Uint8Array(arrayBuffer)
      console.log('[loadTextPreview] 获取到数据, 字节数:', uint8Array.length, '前10字节:', Array.from(uint8Array.slice(0, 10)).map(b => b.toString(16).padStart(2, '0')).join(' '))
      
      // 智能编码检测
      const detectEncoding = (data) => {
        // 先尝试 UTF-8 解码
        const utf8Decoder = new TextDecoder('utf-8', { fatal: false })
        const utf8Text = utf8Decoder.decode(data)
        
        // 检查是否有 UTF-8 替换字符（说明不是有效的 UTF-8）
        const hasReplacementChar = utf8Text.includes('\uFFFD')
        
        // 检查是否有 GBK 特征的高位字节（0x80-0xFF 范围内的字节）
        let hasHighBytes = false
        for (let i = 0; i < Math.min(data.length, 1000); i++) {
          if (data[i] > 0x7F) {
            hasHighBytes = true
            break
          }
        }
        
        console.log('[编码检测] hasReplacementChar:', hasReplacementChar, 'hasHighBytes:', hasHighBytes)
        
        // 如果有替换字符或有高位字节，尝试 GBK
        if (hasReplacementChar || hasHighBytes) {
          try {
            const gbkDecoder = new TextDecoder('gbk', { fatal: false })
            const gbkText = gbkDecoder.decode(data)
            
            // 检查 GBK 解码结果是否包含常见中文字符
            const chinesePattern = /[\u4e00-\u9fa5]/
            const hasChinese = chinesePattern.test(gbkText)
            
            console.log('[编码检测] GBK解码包含中文:', hasChinese, '预览:', gbkText.substring(0, 50))
            
            // 如果 GBK 解码出中文，使用 GBK
            if (hasChinese) {
              return 'gbk'
            }
          } catch (e) {
            console.log('[编码检测] GBK解码失败:', e)
          }
        }
        
        // 默认返回 UTF-8
        return 'utf-8'
      }
      
      const encoding = detectEncoding(uint8Array)
      console.log('[编码检测] 最终选择编码:', encoding)
      const decoder = new TextDecoder(encoding)
      textContent.value = decoder.decode(uint8Array)
    } else {
      textError.value = '预览地址不存在'
    }
  } catch (error) {
    textError.value = error.message || '无法读取文件内容'
  } finally {
    textLoading.value = false
  }
}

const loadWordPreview = async () => {
  wordContent.value = ''
  officeError.value = ''

  if (!props.modelValue || previewType.value !== 'word') return

  officeLoading.value = true
  try {
    const response = await fetch(props.previewUrl)
    if (!response.ok) {
      throw new Error('读取文件失败')
    }
    const arrayBuffer = await response.arrayBuffer()
    const result = await mammoth.convertToHtml({ arrayBuffer })
    wordContent.value = result.value || '<p style="color:#909399">文档内容为空或无法解析</p>'
  } catch (error) {
    officeError.value = error.message || '无法解析 Word 文档'
  } finally {
    officeLoading.value = false
  }
}

const loadExcelPreview = async () => {
  excelData.value = []
  excelColumns.value = []
  excelSheets.value = []
  currentSheet.value = ''
  excelWorkbook.value = null
  officeError.value = ''

  if (!props.modelValue || previewType.value !== 'excel') return

  officeLoading.value = true
  try {
    const response = await fetch(props.previewUrl)
    if (!response.ok) {
      throw new Error('读取文件失败')
    }
    const arrayBuffer = await response.arrayBuffer()
    const workbook = XLSX.read(arrayBuffer, { type: 'array' })
    excelWorkbook.value = workbook

    excelSheets.value = workbook.SheetNames.map(name => ({ name }))

    if (workbook.SheetNames.length > 0) {
      switchSheet(workbook.SheetNames[0])
    }
  } catch (error) {
    officeError.value = error.message || '无法解析 Excel 文档'
  } finally {
    officeLoading.value = false
  }
}

const switchSheet = (sheetName) => {
  if (!excelWorkbook.value) return
  currentSheet.value = sheetName
  const worksheet = excelWorkbook.value.Sheets[sheetName]
  const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 })

  if (jsonData.length === 0) {
    excelData.value = []
    excelColumns.value = []
    return
  }

  const headers = jsonData[0] || []
  excelColumns.value = headers.map((h, i) => h || `列${i + 1}`)

  excelData.value = jsonData.slice(1).map((row, rowIndex) => {
    const obj = {}
    headers.forEach((h, colIndex) => {
      const key = h || `列${colIndex + 1}`
      obj[key] = row[colIndex] !== undefined ? String(row[colIndex]) : ''
    })
    return obj
  })
}

watch(
  () => [props.modelValue, props.previewUrl, props.file?.id, previewType.value],
  () => {
    loadTextPreview()
    loadWordPreview()
    loadExcelPreview()
  },
  { immediate: true }
)
</script>

<style scoped>
.image-preview {
  text-align: center;
}

.image-preview img {
  max-width: 100%;
  max-height: 70vh;
}

.pdf-preview {
  width: 100%;
  height: 75vh;
  border: none;
}

.media-preview {
  max-width: 100%;
  max-height: 75vh;
}

.audio-preview {
  width: 100%;
}

.text-preview-wrapper {
  min-height: 180px;
}

.text-preview {
  max-height: 70vh;
  overflow: auto;
  background: #f5f5f5;
  padding: 16px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.office-preview-wrapper {
  min-height: 180px;
}

.word-preview {
  max-height: 70vh;
  overflow: auto;
  background: #fff;
  padding: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  line-height: 1.8;
}

.word-preview :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
}

.word-preview :deep(table td),
.word-preview :deep(table th) {
  border: 1px solid #ddd;
  padding: 8px;
}

.word-preview :deep(img) {
  max-width: 100%;
}

.excel-preview {
  max-height: 70vh;
  overflow: auto;
}

.sheet-tabs {
  margin-top: 12px;
  padding: 8px 0;
  border-top: 1px solid #e4e7ed;
}

.ppt-actions {
  margin-top: 20px;
  text-align: center;
}

.unsupported-preview {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #606266;
  text-align: center;
}

.unsupported-preview p {
  margin: 0;
}
</style>
