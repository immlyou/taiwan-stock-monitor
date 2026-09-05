import { fetchAPI } from './client'

export const XGBOOST_REQUEST_TIMEOUT_MS = 45_000

export function fetchXGBoost<T>(path: string): Promise<T> {
  // 模型 endpoint 有後端 single-flight；前端逾時後改由使用者決定是否重試，
  // 避免 45 秒預算被隱性放大成兩次嘗試。
  return fetchAPI<T>(path, undefined, XGBOOST_REQUEST_TIMEOUT_MS, 0)
}
