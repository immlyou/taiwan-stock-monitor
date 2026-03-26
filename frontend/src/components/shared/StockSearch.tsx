'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { Search } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { cn } from '@/lib/utils'

interface SearchResult {
  // API 可能回傳 stock_id 或 code（相容兩種格式）
  stock_id?: string
  code?: string
  name: string
  industry?: string
}

export function StockSearch() {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const search = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([])
      setIsOpen(false)
      return
    }
    setIsLoading(true)
    try {
      const apiBase = typeof window !== 'undefined' ? '/api' : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
      const res = await fetch(`${apiBase}/stocks/search?q=${encodeURIComponent(q)}`)
      if (res.ok) {
        const data = await res.json()
        // 相容 {stocks: [...]} 格式及直接陣列格式
        const list = Array.isArray(data) ? data : (data.stocks ?? [])
        setResults(list.slice(0, 50))
        setIsOpen(true)
      }
    } catch {
      setResults([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value
      setQuery(value)
      setActiveIndex(-1)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => search(value), 300)
    },
    [search]
  )

  const handleSelect = useCallback(
    (result: SearchResult) => {
      const id = result.stock_id ?? result.code ?? ''
      setQuery(`${id} ${result.name}`)
      setIsOpen(false)
      router.push(`/stock/${id}`)
    },
    [router]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) return
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        const next = Math.min(activeIndex + 1, results.length - 1)
        setActiveIndex(next)
        document.getElementById(`header-search-${next}`)?.scrollIntoView({ block: 'nearest' })
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        const prev = Math.max(activeIndex - 1, -1)
        setActiveIndex(prev)
        if (prev >= 0) document.getElementById(`header-search-${prev}`)?.scrollIntoView({ block: 'nearest' })
      } else if (e.key === 'Enter' && activeIndex >= 0) {
        e.preventDefault()
        handleSelect(results[activeIndex])
      } else if (e.key === 'Escape') {
        setIsOpen(false)
      }
    },
    [isOpen, results, activeIndex, handleSelect]
  )

  // 點擊外部關閉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4"
          style={{ color: 'var(--muted-foreground)' }}
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => query && results.length > 0 && setIsOpen(true)}
          placeholder="搜尋股票代號或名稱..."
          className={cn(
            'w-full h-9 pl-9 pr-4 rounded-md text-sm outline-none transition-colors',
            'focus:ring-1'
          )}
          style={{
            background: 'var(--secondary)',
            color: 'var(--foreground)',
            border: '1px solid var(--border)',
          }}
          aria-label="搜尋股票"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          role="combobox"
        />
        {isLoading && (
          <div
            className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 rounded-full border-2 border-t-transparent animate-spin"
            style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent' }}
          />
        )}
      </div>

      {/* 下拉結果 */}
      {isOpen && results.length > 0 && (
        <div
          className="absolute top-full left-0 right-0 mt-1 rounded-md border shadow-lg z-50"
          style={{
            background: 'var(--card)',
            borderColor: 'var(--border)',
            maxHeight: 400,
            overflowY: 'auto',
            overscrollBehavior: 'contain',
          }}
          role="listbox"
        >
          <div
            className="px-3 py-1.5 text-xs sticky top-0"
            style={{ color: 'var(--muted-foreground)', background: 'var(--card)', borderBottom: '1px solid var(--border)' }}
          >
            找到 {results.length} 筆{results.length >= 50 ? '（顯示前 50 筆）' : ''}
            <span className="ml-2" style={{ color: 'var(--primary)' }}>↑↓ 選擇 · Enter 前往</span>
          </div>
          {results.map((result, index) => {
            const id = result.stock_id ?? result.code ?? ''
            return (
              <button
                key={id}
                id={`header-search-${index}`}
                onMouseDown={(e) => { e.preventDefault(); handleSelect(result) }}
                onMouseEnter={() => setActiveIndex(index)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 text-sm text-left transition-colors'
                )}
                style={{
                  background: index === activeIndex ? 'var(--secondary)' : undefined,
                  color: 'var(--foreground)',
                  borderBottom: '1px solid var(--border)',
                }}
                role="option"
                aria-selected={index === activeIndex}
              >
                <span
                  className="font-mono font-semibold text-xs px-1.5 py-0.5 rounded shrink-0"
                  style={{ background: 'var(--secondary)', color: 'var(--primary)' }}
                >
                  {id}
                </span>
                <span className="flex-1 truncate">{result.name}</span>
                {result.industry && (
                  <span className="text-xs shrink-0" style={{ color: 'var(--muted-foreground)' }}>
                    {result.industry}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
