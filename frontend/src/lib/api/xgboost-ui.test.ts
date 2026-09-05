import { describe, expect, it } from 'vitest'

import { ApiError } from './client'
import { getXGBoostErrorPresentation } from './xgboost-ui'

describe('XGBoost error presentation', () => {
  it('identifies a model timeout', () => {
    expect(
      getXGBoostErrorPresentation(new DOMException('aborted', 'AbortError'))
    ).toEqual({
      kind: 'timeout',
      message: '模型運算逾時，可能仍在背景完成中。請稍後重試。',
    })
  })

  it('identifies an upstream 504 as a model timeout', () => {
    const error = new ApiError(504, JSON.stringify({ error: 'upstream_timeout' }))

    expect(getXGBoostErrorPresentation(error)).toEqual({
      kind: 'timeout',
      message: '模型運算逾時，可能仍在背景完成中。請稍後重試。',
    })
  })

  it('identifies a missing backend dependency', () => {
    const error = new ApiError(
      503,
      JSON.stringify({
        detail: 'XGBoost 模型不可用：No module named xgboost，請確認 xgboost 與 scikit-learn 已安裝',
      })
    )

    expect(getXGBoostErrorPresentation(error)).toEqual({
      kind: 'dependency',
      message: 'XGBoost 執行環境缺少必要依賴，請檢查後端部署。',
    })
  })

  it('identifies a temporary service failure without blaming dependencies', () => {
    const error = new ApiError(
      503,
      JSON.stringify({ detail: 'upstream temporarily unavailable' })
    )

    expect(getXGBoostErrorPresentation(error)).toEqual({
      kind: 'temporary',
      message: '模型服務暫時不可用，請稍後重試。',
    })
  })
})
