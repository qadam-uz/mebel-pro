import { ref } from 'vue'
import { defineStore } from 'pinia'

import { api, apiTraceId, withQuery } from '@/shared/api/client'
import { useAuthStore } from '@/shared/stores/auth'

export interface UploadedFile {
  id: string
  original_name: string
  content_type: string
  size_bytes: number
  storage_status: 'pending' | 'stored' | 'deleted'
  entity_type: string | null
  entity_id: string | null
  uploaded_by_type: 'platform_user' | 'workshop_user' | 'client'
  uploaded_by_id: string
  created_at: string
  updated_at: string
}

export const useFilesStore = defineStore('files', () => {
  const uploading = ref(false)
  const error = ref<string | null>(null)
  const traceId = ref<string | null>(null)
  const auth = useAuthStore()

  async function upload(file: File) {
    uploading.value = true
    error.value = null
    traceId.value = null
    const formData = new FormData()
    formData.set('upload', file)
    try {
      return await api.postForm<UploadedFile>('/files', formData, {
        accessToken: auth.accessToken,
      })
    } catch (errorValue) {
      error.value = 'file_upload_failed'
      traceId.value = apiTraceId(errorValue)
      throw error.value
    } finally {
      uploading.value = false
    }
  }

  // Returns a disposable handle, not a bare URL string (CB-131): the object URL
  // pins the decoded blob until revoked, so the caller MUST call `revoke()` when
  // the image is gone (e.g. onBeforeUnmount). Returning the revoke makes that
  // ownership contract explicit and impossible to forget silently.
  async function loadObjectUrl(
    fileId: string,
    size: 'sm' | 'md' | 'original' = 'original',
  ): Promise<{ url: string; revoke: () => void }> {
    // `original` sends no parameter, keeping the URL — and therefore the browser
    // cache entry — identical to what shipped before renditions existed.
    const blob = await api.blob(
      size === 'original' ? `/files/${fileId}` : withQuery(`/files/${fileId}`, { size }),
      { accessToken: auth.accessToken },
    )
    const url = URL.createObjectURL(blob)
    return { url, revoke: () => URL.revokeObjectURL(url) }
  }

  function reset() {
    uploading.value = false
    error.value = null
    traceId.value = null
  }

  return { uploading, error, traceId, upload, loadObjectUrl, reset }
})
