import { describe, expect, it } from 'vitest'

import { parseSettingsResponse } from './settings'

const backendContract = {
  theme: 'light',
  language: 'zh-TW',
  notifications_enabled: true,
  default_days: 60,
  telegram: {
    enabled: true,
    chatId: '123456',
    botTokenConfigured: true,
  },
  email: {
    enabled: false,
    smtpHost: 'smtp.gmail.com',
    smtpPort: 587,
    username: '',
    recipient: '',
    passwordConfigured: false,
  },
  system: {
    dataUpdateInterval: 30,
    timezone: 'Asia/Taipei',
    autoBacktest: false,
    marketOpenTime: '09:00',
    marketCloseTime: '13:30',
  },
}

describe('settings API contract', () => {
  it('accepts the backend settings response', () => {
    expect(parseSettingsResponse(backendContract)).toEqual(backendContract)
  })

  it('rejects responses that expose notification secrets', () => {
    expect(() => parseSettingsResponse({
      ...backendContract,
      telegram: { ...backendContract.telegram, botToken: 'leaked' },
    })).toThrow(/secret/i)
    expect(() => parseSettingsResponse({
      ...backendContract,
      email: { ...backendContract.email, password: 'leaked' },
    })).toThrow(/secret/i)
  })

  it('rejects a drifted or incomplete response', () => {
    expect(() => parseSettingsResponse({ ...backendContract, system: {} })).toThrow(
      /settings contract/i,
    )
  })
})
