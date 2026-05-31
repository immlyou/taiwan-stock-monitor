interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
  /** 自動依首尾值決定漲跌色（紅漲綠跌），覆寫 color */
  autoColor?: boolean
  className?: string
}

/**
 * 迷你走勢圖（純 SVG，無外部依賴）。用於 KPI 卡片、清單列等小空間趨勢呈現。
 */
export function Sparkline({
  data,
  width = 64,
  height = 22,
  color = 'var(--primary)',
  autoColor = false,
  className,
}: SparklineProps) {
  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const stepX = width / (data.length - 1)
  const pad = 2

  const points = data
    .map((v, i) => {
      const x = i * stepX
      const y = height - pad - ((v - min) / range) * (height - pad * 2)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  const stroke = autoColor
    ? data[data.length - 1] >= data[0]
      ? 'var(--stock-up)'
      : 'var(--stock-down)'
    : color

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      style={{ display: 'block', overflow: 'visible' }}
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
