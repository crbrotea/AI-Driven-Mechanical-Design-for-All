import { describe, it, expect } from 'vitest'
import enMessages from '@/messages/en.json'
import esMessages from '@/messages/es.json'
import { LOCALES } from './config'

describe('i18n', () => {
  it('has en and es locales configured', () => {
    expect(LOCALES).toEqual(['en', 'es'])
  })

  it('en and es message files have identical keys', () => {
    const flatten = (obj: any, prefix = ''): string[] =>
      Object.entries(obj).flatMap(([k, v]) =>
        typeof v === 'object' && v !== null
          ? flatten(v, prefix ? `${prefix}.${k}` : k)
          : [prefix ? `${prefix}.${k}` : k]
      )
    const enKeys = flatten(enMessages).sort()
    const esKeys = flatten(esMessages).sort()
    expect(esKeys).toEqual(enKeys)
  })
})
