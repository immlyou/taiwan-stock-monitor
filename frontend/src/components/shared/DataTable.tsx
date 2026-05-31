'use client'

import * as React from 'react'
import {
  type ColumnDef,
  type SortingState,
  type Table as TanstackTable,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import {
  ArrowDown,
  ArrowUp,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Search,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

export interface DataTableProps<T> {
  /** TanStack column definitions */
  columns: ColumnDef<T, unknown>[]
  /** Row data */
  data: T[]
  /** Show the global search input above the table. Default: false */
  searchable?: boolean
  /** Placeholder text for the search input */
  searchPlaceholder?: string
  /** Show the CSV export button above the table. Default: false */
  exportable?: boolean
  /** Filename (without extension) for the exported CSV. Default: 'export' */
  exportFilename?: string
  /** Rows per page. Default: 20 */
  pageSize?: number
  /** Text shown when there is no data. Default: '無資料' */
  emptyMessage?: string
  /** Extra className for the outer scroll container */
  className?: string
}

/**
 * Resolve a human-readable header label for CSV export.
 */
function getColumnLabel<T>(column: ColumnDef<T, unknown>, index: number): string {
  const header = column.header
  if (typeof header === 'string') return header
  const id =
    column.id ??
    ('accessorKey' in column && typeof column.accessorKey === 'string'
      ? column.accessorKey
      : undefined)
  return id ?? `欄位${index + 1}`
}

/**
 * Escape a single CSV field per RFC 4180.
 */
function escapeCsvField(value: unknown): string {
  if (value == null) return ''
  const str = String(value)
  if (/[",\n\r]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/**
 * Build CSV text from the currently filtered + sorted rows and trigger a
 * pure client-side Blob download.
 */
function exportToCsv<T>(
  table: TanstackTable<T>,
  columns: ColumnDef<T, unknown>[],
  filename: string
): void {
  const headers = columns.map((col, i) => getColumnLabel(col, i))

  // 匯出目前「過濾 + 排序後」的所有列，與畫面顯示順序一致
  const rows = table.getSortedRowModel().rows.map((row) =>
    row.getVisibleCells().map((cell) => {
      const value = cell.getValue()
      return escapeCsvField(value)
    })
  )

  const csv = [headers.map(escapeCsvField), ...rows]
    .map((cells) => cells.join(','))
    .join('\r\n')

  // Prepend BOM so Excel reads UTF-8 (Chinese) correctly.
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${filename}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function DataTable<T>({
  columns,
  data,
  searchable = false,
  searchPlaceholder = '搜尋...',
  exportable = false,
  exportFilename = 'export',
  pageSize = 20,
  emptyMessage = '無資料',
  className,
}: DataTableProps<T>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = React.useState('')

  const table = useReactTable<T>({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  })

  const showToolbar = searchable || exportable
  const rows = table.getRowModel().rows
  const pageCount = table.getPageCount()
  const pageIndex = table.getState().pagination.pageIndex

  return (
    <div className="w-full space-y-3">
      {showToolbar && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          {searchable ? (
            <div className="relative w-full sm:max-w-xs">
              <Search
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2"
                style={{ color: 'var(--muted-foreground)' }}
                aria-hidden="true"
              />
              <Input
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                placeholder={searchPlaceholder}
                aria-label={searchPlaceholder}
                className="pl-9"
              />
            </div>
          ) : (
            <div />
          )}

          {exportable && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => exportToCsv(table, columns, exportFilename)}
              disabled={table.getFilteredRowModel().rows.length === 0}
            >
              <Download aria-hidden="true" />
              匯出 CSV
            </Button>
          )}
        </div>
      )}

      <div
        className={cn(
          'relative w-full overflow-x-auto rounded-md border',
          className
        )}
        style={{ borderColor: 'var(--border)' }}
      >
        <Table>
          <TableHeader
            className="sticky top-0 z-10"
            style={{ backgroundColor: 'var(--card)' }}
          >
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort()
                  const sorted = header.column.getIsSorted()
                  return (
                    <TableHead
                      key={header.id}
                      style={{ width: header.getSize() }}
                      aria-sort={
                        sorted === 'asc'
                          ? 'ascending'
                          : sorted === 'desc'
                            ? 'descending'
                            : canSort
                              ? 'none'
                              : undefined
                      }
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex select-none items-center gap-1 rounded transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                          {sorted === 'asc' ? (
                            <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                          ) : sorted === 'desc' ? (
                            <ArrowDown
                              className="h-3.5 w-3.5"
                              aria-hidden="true"
                            />
                          ) : (
                            <ChevronsUpDown
                              className="h-3.5 w-3.5 opacity-50"
                              aria-hidden="true"
                            />
                          )}
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )
                      )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.length ? (
              rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && 'selected'}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="tabular-nums">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell
                  colSpan={columns.length || 1}
                  className="h-24 text-center"
                  style={{ color: 'var(--muted-foreground)' }}
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
            第 {pageIndex + 1} / {pageCount} 頁
          </p>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              aria-label="上一頁"
            >
              <ChevronLeft aria-hidden="true" />
              上一頁
            </Button>
            <span className="px-2 text-sm tabular-nums">{pageIndex + 1}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              aria-label="下一頁"
            >
              下一頁
              <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default DataTable
