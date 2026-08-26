import { ApiError } from './client'

export type XGBoostErrorKind = 'timeout' | 'temporary' | 'dependency'

export interface XGBoostErrorPresentation {
  kind: XGBoostErrorKind
  message: string
}

export function getXGBoostErrorPresentation(
  error: unknown
): XGBoostErrorPresentation {
  const errorName = error instanceof Error ? error.name : ''
  if (errorName === 'AbortError' || (error instanceof ApiError && error.status === 504)) {
    return {
      kind: 'timeout',
      message: '模型運算逾時，可能仍在背景完成中。請稍後重試。',
    }
  }

  const rawMessage = error instanceof Error ? error.message : String(error ?? '')
  const dependencyFailure =
    error instanceof ApiError &&
    error.status === 503 &&
    /XGBoost 模型不可用|No module named|xgboost[^\n]*(未安裝|not installed)|scikit-learn[^\n]*(未安裝|not installed)/i.test(
      rawMessage
    )

  if (dependencyFailure) {
    return {
      kind: 'dependency',
      message: 'XGBoost 執行環境缺少必要依賴，請檢查後端部署。',
    }
  }

  return {
    kind: 'temporary',
    message: '模型服務暫時不可用，請稍後重試。',
  }
}
