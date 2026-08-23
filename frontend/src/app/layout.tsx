import type { Metadata } from 'next'
import './globals.css'
import { AppShell } from '@/components/layout/AppShell'
import { Providers } from '@/components/Providers'

export const metadata: Metadata = {
  title: '台股監控系統',
  description: '台灣股票市場即時監控與分析平台',
}

// 三套主題字體（sans / serif / mono + Noto TC 中文）；weights 400/500/600/700。
const FONTS_HREF =
  'https://fonts.googleapis.com/css2?' +
  'family=IBM+Plex+Sans:wght@400;500;600;700&' +
  'family=IBM+Plex+Mono:wght@400;500;600;700&' +
  'family=Spectral:wght@400;500;600;700&' +
  'family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600;6..72,700&' +
  'family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600;8..60,700&' +
  'family=Manrope:wght@400;500;600;700&' +
  'family=Noto+Sans+TC:wght@400;500;600;700&' +
  'family=Noto+Serif+TC:wght@400;500;600;700&display=swap'

// 首屏前（paint 之前）依 localStorage 套好主題與深淺，避免 FOUC / 主題閃跳。
const NO_FLASH_SCRIPT = `(function(){try{
var t=localStorage.getItem('tw_theme')||'terminal';
var def={terminal:'dark',editorial:'light',slate:'dark'};
var m=localStorage.getItem('tw_mode')||def[t]||'dark';
var d=document.documentElement;d.dataset.theme=t;d.dataset.mode=m;
}catch(e){var d=document.documentElement;d.dataset.theme='terminal';d.dataset.mode='dark';}})();`

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="zh-TW" className="h-full" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={FONTS_HREF} />
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_SCRIPT }} />
      </head>
      <body className="h-full" style={{ background: 'var(--background)', color: 'var(--foreground)' }}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  )
}
