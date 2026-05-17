import { describe, expect, it } from 'vitest'
import {
  ALLOWED_IMAGE_MIME,
  MAX_IMAGE_BYTES,
  formatBytes,
  isAllowedMime,
  readFileAsAttachment,
} from './chat-attachment'

function makeFile(name: string, type: string, size: number): File {
  // jsdom File doesn't honor explicit size on Uint8Array — pad bytes directly.
  const bytes = new Uint8Array(size)
  return new File([bytes], name, { type })
}

describe('isAllowedMime', () => {
  it.each(ALLOWED_IMAGE_MIME)('accepts %s', (mime) => {
    expect(isAllowedMime(mime)).toBe(true)
  })
  it('rejects image/gif', () => {
    expect(isAllowedMime('image/gif')).toBe(false)
  })
  it('rejects application/pdf', () => {
    expect(isAllowedMime('application/pdf')).toBe(false)
  })
})

describe('readFileAsAttachment', () => {
  it('returns bad_type for unsupported mime', async () => {
    const file = makeFile('a.gif', 'image/gif', 1024)
    const result = await readFileAsAttachment(file)
    expect(result).toBe('bad_type')
  })

  it('returns too_large when file exceeds 4 MiB', async () => {
    const file = makeFile('big.png', 'image/png', MAX_IMAGE_BYTES + 1)
    const result = await readFileAsAttachment(file)
    expect(result).toBe('too_large')
  })

  it('returns full attachment for a valid PNG', async () => {
    const file = makeFile('sketch.png', 'image/png', 1024)
    const result = await readFileAsAttachment(file)
    expect(typeof result).toBe('object')
    if (typeof result === 'object') {
      expect(result.mime).toBe('image/png')
      expect(result.dataUrl.startsWith('data:image/png;base64,')).toBe(true)
      expect(result.b64.length).toBeGreaterThan(0)
      expect(result.b64).not.toContain(',')
    }
  })
})

describe('formatBytes', () => {
  it('formats small byte counts', () => {
    expect(formatBytes(512)).toBe('512 B')
  })
  it('formats KB', () => {
    expect(formatBytes(2048)).toBe('2 KB')
  })
  it('formats MB', () => {
    expect(formatBytes(2 * 1024 * 1024)).toBe('2.0 MB')
  })
})
