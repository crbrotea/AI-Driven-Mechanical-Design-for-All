export const ALLOWED_IMAGE_MIME = ['image/png', 'image/jpeg', 'image/webp'] as const
export const MAX_IMAGE_BYTES = 4 * 1024 * 1024 // 4 MiB

export type AllowedImageMime = (typeof ALLOWED_IMAGE_MIME)[number]

export type ChatAttachment = {
  file: File
  dataUrl: string
  b64: string
  mime: AllowedImageMime
}

export type AttachmentError = 'too_large' | 'bad_type'

export function isAllowedMime(mime: string): mime is AllowedImageMime {
  return (ALLOWED_IMAGE_MIME as readonly string[]).includes(mime)
}

export async function readFileAsAttachment(
  file: File,
): Promise<ChatAttachment | AttachmentError> {
  if (!isAllowedMime(file.type)) return 'bad_type'
  if (file.size > MAX_IMAGE_BYTES) return 'too_large'

  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })

  const comma = dataUrl.indexOf(',')
  const b64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl

  return { file, dataUrl, b64, mime: file.type }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
