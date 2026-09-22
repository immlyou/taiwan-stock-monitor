export type AccountRole = 'admin' | 'member' | 'viewer'
export interface Account {
  id: string
  email: string
  user_id: string | null
  name: string
  role: AccountRole
  enabled: boolean
  created_at: string
  last_login_at: string | null
  revision: number
}
export interface AccountList {
  accounts: Account[]
  audit: { at: string; actor: string; action: string; email: string; role: AccountRole; enabled: boolean }[]
}
export const ROLE_LABELS: Record<AccountRole, string> = {
  admin: '管理員', member: '一般使用者', viewer: '唯讀',
}
