'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StockSearchResult {
  stock_id: string
  name: string
  industry?: string
}

interface StockSearchResponse {
  query: string
  total: number
  stocks: StockSearchResult[]
}

interface StockInputProps {
  value: string
  onChange: (stockId: string) => void
  placeholder?: string
  label?: string
  className?: string
}

export function StockInput({
  value,
  onChange,
  placeholder = '輸入代號或中文名稱，例：2330 或 台積電',
  label,
  className,
}: StockInputProps) {
  const [query, setQuery] = useState(() => value ? value : '')
  const [results, setResults] = useState<StockSearchResult[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 當外部 value 清空時同步清空輸入框顯示
  useEffect(() => {
    if (!value) {
      setQuery('')
    }
  }, [value])

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
        const data: StockSearchResponse | StockSearchResult[] = await res.json()
        // API 可能回傳 {stocks: [...]} 或直接回傳陣列
        const stocks = Array.isArray(data)
          ? (data as StockSearchResult[]).slice(0, 8)
          : ((data as StockSearchResponse).stocks ?? []).slice(0, 8)
        setResults(stocks)
        if (stocks.length > 0) setIsOpen(true)
      }
    } catch {
      setResults([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value
      setQuery(val)
      setActiveIndex(-1)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => search(val), 300)
    },
    [search]
  )

  const handleSelect = useCallback(
    (result: StockSearchResult) => {
      setQuery(`${result.stock_id} ${result.name}`)
      setIsOpen(false)
      setResults([])
      onChange(result.stock_id)
    },
    [onChange]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((prev) => Math.min(prev + 1, results.length - 1))
        if (!isOpen && results.length > 0) setIsOpen(true)
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((prev) => Math.max(prev - 1, -1))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        if (isOpen && results.length > 0) {
          const idx = activeIndex >= 0 ? activeIndex : 0
          handleSelect(results[idx])
        }
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
    <div ref={containerRef} className={cn('relative', className)}>
      {label && (
        <label className="block text-xs mb-1" style={{ color: 'var(--muted-foreground)' }}>
          {label}
        </label>
      )}
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 pointer-events-none"
          style={{ color: 'var(--muted-foreground)' }}
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (query && results.length > 0) setIsOpen(true)
          }}
          placeholder={placeholder}
          className="h-9 w-full pl-9 pr-4 rounded-md text-sm outline-none transition-colors focus:ring-1"
          style={{
            background: 'var(--background)',
            color: 'var(--foreground)',
            border: '1px solid var(--border)',
          }}
          aria-label="搜尋股票"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          role="combobox"
          autoComplete="off"
        />
        {isLoading && (
          <div
            className="absolute right-3 top-1/2 -translate-y-1/2 h-3 w-3 rounded-full border-2 animate-spin"
            style={{ borderColor: 'var(--primary)', borderTopColor: 'transparent' }}
          />
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div
          className="absolute top-full left-0 right-0 mt-1 rounded-md border shadow-lg z-50 overflow-hidden"
          style={{
            background: 'var(--card)',
            borderColor: 'var(--border)',
          }}
          role="listbox"
        >
          {results.map((result, index) => (
            <button
              key={result.stock_id}
              onMouseDown={(e) => {
                // 用 mousedown 避免 blur 搶先觸發
                e.preventDefault()
                handleSelect(result)
              }}
              className="w-full flex items-center gap-3 px-3 py-2 text-sm text-left transition-colors"
              style={{
                background: index === activeIndex ? 'var(--secondary)' : undefined,
                color: 'var(--foreground)',
              }}
              role="option"
              aria-selected={index === activeIndex}
            >
              <span
                className="font-mono font-semibold text-xs px-1.5 py-0.5 rounded shrink-0"
                style={{ background: 'var(--secondary)', color: 'var(--primary)' }}
              >
                {result.stock_id}
              </span>
              <span className="flex-1 truncate">{result.name}</span>
              {result.industry && (
                <span className="text-xs shrink-0" style={{ color: 'var(--muted-foreground)' }}>
                  {result.industry}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
