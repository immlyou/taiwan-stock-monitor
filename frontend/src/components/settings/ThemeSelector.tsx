'use client'

import { useSyncExternalStore } from 'react'
import { Check, Sun, Moon } from 'lucide-react'
import { useAppStore, type ThemeName, type ModeName } from '@/store/useAppStore'

// 僅在 client 為 true 的旗標（hydration-safe，不用 setState-in-effect）。
const emptySubscribe = () => () => {}
function useMounted(): boolean {
  return useSyncExternalStore(emptySubscribe, () => true, () => false)
}

// 各主題卡片預覽用其「招牌模式」的實色（直接寫死，讓卡片不受目前啟用主題影響）。
interface ThemePreview {
  id: ThemeName
  name: string
  desc: string
  bg: string
  card: string
  accent: string
  up: string
  down: string
  fg: string
  muted: string
  serif: string
  radius: number
}

const THEMES: ThemePreview[] = [
  {
    id: 'terminal',
    name: '終端金',
    desc: '近黑底 · 琥珀金 · 等寬數據，Bloomberg 終端感',
    bg: '#0A0A0C', card: '#15151B', accent: '#E8A33D', up: '#FF4D4D', down: '#1FBF75',
    fg: '#E8E6DE', muted: '#8E8B83', serif: "'Spectral', serif", radius: 4,
  },
  {
    id: 'editorial',
    name: '編輯帳冊',
    desc: '米色紙感 · 大襯線標題 · 沉穩金，財經報刊權威',
    bg: '#F5F0E6', card: '#FFFFFF', accent: '#9A6A1F', up: '#C8362B', down: '#1E7A4D',
    fg: '#1C1815', muted: '#6F6557', serif: "'Newsreader', serif", radius: 5,
  },
  {
    id: 'slate',
    name: '石墨黃銅',
    desc: '石墨深色 · 圓角柔光 · 黃銅點綴，精緻 fintech',
    bg: '#13151B', card: '#1B1E26', accent: '#C9A227', up: '#FF5252', down: '#2BD27C',
    fg: '#E8EAEF', muted: '#8B93A3', serif: "'Source Serif 4', serif", radius: 13,
  },
]

function Swatch({ color }: { color: string }) {
  return (
    <span
      className="inline-block h-4 w-4 rounded-full"
      style={{ background: color, boxShadow: '0 0 0 1px rgba(0,0,0,0.15) inset' }}
    />
  )
}

export function ThemeSelector() {
  const { theme, mode, setTheme, setMode } = useAppStore()
  // 避免 SSR/CSR 選中態不一致：mount 後才反映實際 active 主題。
  const mounted = useMounted()

  return (
    <div
      className="rounded-lg p-4"
      style={{ background: 'var(--card)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold" style={{ color: 'var(--foreground)' }}>佈景主題</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
            三套機構級終端風格，深／淺雙模式，選擇會記在這台裝置
          </p>
        </div>

        {/* 深/淺分段切換 */}
        <div className="flex gap-1 p-1 rounded-md" style={{ background: 'var(--secondary)' }}>
          {([
            { m: 'light' as ModeName, icon: Sun, label: '淺色' },
            { m: 'dark' as ModeName, icon: Moon, label: '深色' },
          ]).map(({ m, icon: Icon, label }) => {
            const active = mounted && mode === m
            return (
              <button
                key={m}
                onClick={() => setMode(m)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors"
                style={{
                  background: active ? 'var(--card)' : 'transparent',
                  color: active ? 'var(--primary)' : 'var(--muted-foreground)',
                  boxShadow: active ? '0 1px 2px rgba(0,0,0,0.2)' : 'none',
                }}
                aria-pressed={active}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {/* 三張主題卡片 */}
      <div className="grid gap-3 sm:grid-cols-3">
        {THEMES.map((t) => {
          const selected = mounted && theme === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              className="relative text-left rounded-lg overflow-hidden transition-all"
              style={{
                border: selected ? `2px solid ${t.accent}` : '2px solid var(--border)',
                boxShadow: selected ? `0 0 0 3px var(--accent-soft)` : 'none',
              }}
              aria-pressed={selected}
            >
              {/* 選中徽章 */}
              {selected && (
                <span
                  className="absolute right-2 top-2 z-10 flex h-5 w-5 items-center justify-center rounded-full"
                  style={{ background: t.accent, color: '#fff' }}
                >
                  <Check className="h-3 w-3" strokeWidth={3} />
                </span>
              )}

              {/* 上半：該主題實色預覽 */}
              <div className="p-3" style={{ background: t.bg }}>
                <div
                  className="rounded-md p-3"
                  style={{ background: t.card, borderRadius: t.radius }}
                >
                  <div
                    className="text-sm font-semibold mb-1"
                    style={{ color: t.fg, fontFamily: t.serif }}
                  >
                    持倉總覽
                  </div>
                  <div
                    className="text-2xl font-bold mb-2"
                    style={{ color: t.fg, fontFamily: t.serif, fontVariantNumeric: 'tabular-nums' }}
                  >
                    23,415
                    <span className="text-sm font-medium ml-2" style={{ color: t.up }}>+1.82%</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Swatch color={t.accent} />
                    <Swatch color={t.up} />
                    <Swatch color={t.down} />
                    <Swatch color={t.card === '#FFFFFF' ? t.bg : t.card} />
                  </div>
                </div>
              </div>

              {/* 下半：主題名 + 說明 */}
              <div className="px-3 py-2.5" style={{ background: 'var(--card)' }}>
                <div className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{t.name}</div>
                <div className="text-xs mt-0.5 leading-snug" style={{ color: 'var(--muted-foreground)' }}>{t.desc}</div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
