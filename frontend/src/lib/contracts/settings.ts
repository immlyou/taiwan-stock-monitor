export interface SettingsResponse {
  theme: string
  language: string
  notifications_enabled: boolean
  default_days: number
  telegram: {
    enabled: boolean
    chatId: string
    botTokenConfigured: boolean
  }
  email: {
    enabled: boolean
    smtpHost: string
    smtpPort: number
    username: string
    recipient: string
    passwordConfigured: boolean
  }
  system: {
    dataUpdateInterval: number
    timezone: string
    autoBacktest: boolean
    marketOpenTime: string
    marketCloseTime: string
  }
}

export type SettingsForm = Omit<SettingsResponse, 'telegram' | 'email'> & {
  telegram: SettingsResponse['telegram'] & { botToken?: string }
  email: SettingsResponse['email'] & { password?: string }
}

type JsonRecord = Record<string, unknown>

function record(value: unknown): JsonRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Settings contract mismatch')
  }
  return value as JsonRecord
}

function stringField(value: unknown): string {
  if (typeof value !== 'string') throw new Error('Settings contract mismatch')
  return value
}

function numberField(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    throw new Error('Settings contract mismatch')
  }
  return value
}

function booleanField(value: unknown): boolean {
  if (typeof value !== 'boolean') throw new Error('Settings contract mismatch')
  return value
}

export function parseSettingsResponse(value: unknown): SettingsResponse {
  const root = record(value)
  const telegram = record(root.telegram)
  const email = record(root.email)
  const system = record(root.system)

  if ('botToken' in telegram || 'token' in telegram || 'password' in email) {
    throw new Error('Settings response exposed a secret')
  }

  return {
    theme: stringField(root.theme),
    language: stringField(root.language),
    notifications_enabled: booleanField(root.notifications_enabled),
    default_days: numberField(root.default_days),
    telegram: {
      enabled: booleanField(telegram.enabled),
      chatId: stringField(telegram.chatId),
      botTokenConfigured: booleanField(telegram.botTokenConfigured),
    },
    email: {
      enabled: booleanField(email.enabled),
      smtpHost: stringField(email.smtpHost),
      smtpPort: numberField(email.smtpPort),
      username: stringField(email.username),
      recipient: stringField(email.recipient),
      passwordConfigured: booleanField(email.passwordConfigured),
    },
    system: {
      dataUpdateInterval: numberField(system.dataUpdateInterval),
      timezone: stringField(system.timezone),
      autoBacktest: booleanField(system.autoBacktest),
      marketOpenTime: stringField(system.marketOpenTime),
      marketCloseTime: stringField(system.marketCloseTime),
    },
  }
}
