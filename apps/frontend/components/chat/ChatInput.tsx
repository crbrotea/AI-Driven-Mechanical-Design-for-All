'use client'
import { useRef, useState, FormEvent, ChangeEvent } from 'react'
import { useTranslations } from 'next-intl'
import { Paperclip, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { toast } from '@/components/ui/toast'
import {
  ALLOWED_IMAGE_MIME,
  formatBytes,
  readFileAsAttachment,
  type ChatAttachment,
} from '@/lib/chat-attachment'

export function ChatInput({
  onSubmit,
  disabled,
  initialValue = '',
}: {
  onSubmit: (value: string, attachment?: ChatAttachment) => void
  disabled: boolean
  initialValue?: string
}) {
  const t = useTranslations('chat')
  const [value, setValue] = useState(initialValue)
  const [attachment, setAttachment] = useState<ChatAttachment | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  function handle(e: FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed && !attachment) return
    onSubmit(trimmed || '(see attached sketch)', attachment ?? undefined)
    setValue('')
    setAttachment(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const result = await readFileAsAttachment(file)
    if (result === 'bad_type') {
      toast(t('image_bad_type'), 'error')
      e.target.value = ''
      return
    }
    if (result === 'too_large') {
      toast(t('image_too_large'), 'error')
      e.target.value = ''
      return
    }
    setAttachment(result)
  }

  function removeAttachment() {
    setAttachment(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <form onSubmit={handle} className="flex flex-col gap-2 border-t border-border p-3">
      {attachment && (
        <div className="flex items-center gap-2 rounded-md border border-border bg-muted px-2 py-1.5">
          <img
            src={attachment.dataUrl}
            alt=""
            className="h-10 w-10 rounded object-cover"
          />
          <div className="flex flex-col min-w-0">
            <span className="truncate text-xs font-medium" title={attachment.file.name}>
              {attachment.file.name}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {formatBytes(attachment.file.size)}
            </span>
          </div>
          <button
            type="button"
            onClick={removeAttachment}
            className="ml-auto rounded-md p-1 text-muted-foreground hover:bg-background hover:text-foreground"
            aria-label={t('attach_remove')}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      <div className="flex gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept={ALLOWED_IMAGE_MIME.join(',')}
          onChange={onFileChange}
          className="hidden"
          aria-hidden="true"
          tabIndex={-1}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          aria-label={t('attach_aria')}
          title={t('attach_aria')}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t('placeholder')}
          disabled={disabled}
          aria-label={t('placeholder')}
        />
        <Button type="submit" disabled={disabled || (!value.trim() && !attachment)}>
          {t('send')}
        </Button>
      </div>
    </form>
  )
}
