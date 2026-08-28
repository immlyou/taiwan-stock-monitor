import type { LucideIcon } from 'lucide-react'
import {
  Activity,
  ArrowLeftRight,
  Bell,
  Bot,
  Briefcase,
  Building2,
  CandlestickChart,
  Crosshair,
  FileText,
  Gem,
  GitCompare,
  Grid3x3,
  History,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  LineChart,
  Moon,
  NotebookPen,
  PieChart,
  Radar,
  Settings2,
  ShieldAlert,
  Siren,
  SlidersHorizontal,
  Sparkles,
  Star,
  Sunrise,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react'

export interface NavigationItem {
  label: string
  href: string
  icon: LucideIcon
  description: string
  matchPrefix?: string
  isNew?: boolean
}

export interface NavigationGroup {
  label: string
  icon: LucideIcon
  items: readonly NavigationItem[]
}

export const NAVIGATION_GROUPS: readonly NavigationGroup[] = [
  {
    label: '市場動態',
    icon: LayoutGrid,
    items: [
      { label: '市場戰情中心', href: '/', icon: LayoutDashboard, description: '台股大盤、漲跌家數與市場即時總覽' },
      { label: '即時報價', href: '/realtime', icon: Activity, description: 'Fugle / TWSE 即時優先，收盤資料自動備援' },
      { label: '每日晨報', href: '/morning-report', icon: Sunrise, description: '市場總覽、新聞情緒與 AI 分析' },
      { label: '市場熱力圖', href: '/heatmap', icon: Grid3x3, description: '依產業、市值與漲跌幅下鑽市場' },
      { label: '資金流向', href: '/money-flow', icon: ArrowLeftRight, description: '三大法人與市場資金方向' },
      { label: '盤後總覽', href: '/after-hours', icon: Moon, description: '收盤統計與盤後策略候選股' },
    ],
  },
  {
    label: '研究分析',
    icon: LineChart,
    items: [
      { label: '個股分析', href: '/stock/2330', matchPrefix: '/stock', icon: TrendingUp, description: '量化評分、AI 摘要、技術、籌碼與財報' },
      { label: '技術分析', href: '/technical', icon: CandlestickChart, description: '價格走勢與常用技術指標' },
      { label: '比較分析', href: '/compare', icon: GitCompare, description: '多檔股票走勢與指標比較' },
      { label: '產業分析', href: '/industry', icon: Building2, description: '產業輪動、強弱與代表個股' },
      { label: '籌碼分析', href: '/chip', icon: Users, description: '三大法人與籌碼變化明細' },
      { label: '財報分析', href: '/financials', icon: FileText, description: '營收、估值與基本面趨勢' },
      { label: '風險分析', href: '/risk', icon: ShieldAlert, description: '波動率、VaR 與最大回撤' },
    ],
  },
  {
    label: '選股策略',
    icon: Crosshair,
    items: [
      { label: '選股篩選', href: '/screener', icon: SlidersHorizontal, description: '量化排行與條件式篩選' },
      { label: 'AI 智慧選股', href: '/ai-pick', icon: Sparkles, description: 'XGBoost、LSTM 與 Claude 智慧分析', isNew: true },
      { label: 'AI 操盤雷達', href: '/trading-radar', icon: Radar, description: '個股多維度訊號與操盤計畫' },
      { label: '市場異常掃描', href: '/ai-anomaly', icon: Siren, description: '依嚴重度分組的市場異常偵測' },
      { label: '回測分析', href: '/backtest', icon: History, description: '策略歷史績效與風險驗證' },
      { label: '策略管理', href: '/strategies', icon: Layers, description: '自訂策略的建立、保存與管理' },
      { label: '參數優化', href: '/optimizer', icon: Settings2, description: 'Grid Search 尋找策略參數' },
      { label: '預測驗證', href: '/predictions', icon: Target, description: '追蹤預測結果與實際命中率' },
      { label: '遺珠掃描', href: '/hidden-gems', icon: Gem, description: '低估值與營收動能候選股' },
    ],
  },
  {
    label: '投資管理',
    icon: Briefcase,
    items: [
      { label: '持倉總覽', href: '/dashboard', icon: LayoutDashboard, description: '投資組合 KPI、持股明細與自訂 Widget', isNew: true },
      { label: '投資組合', href: '/portfolio', icon: PieChart, description: '持股損益、診斷與 What-if 模擬', isNew: true },
      { label: 'AI 投資顧問', href: '/advisor', icon: Bot, description: '持股健檢、配置建議與一鍵套用', isNew: true },
      { label: '自選股', href: '/watchlist', icon: Star, description: '個人追蹤清單與即時報價', isNew: true },
      { label: '交易日誌', href: '/journal', icon: NotebookPen, description: '交易紀錄與 AI 覆盤報告' },
      { label: '自訂警報', href: '/alerts', icon: Bell, description: '多條件規則、冷卻時間與通知渠道' },
    ],
  },
]

export function isNavigationItemActive(
  item: Pick<NavigationItem, 'href' | 'matchPrefix'>,
  pathname: string
): boolean {
  if (item.matchPrefix) {
    return pathname === item.matchPrefix || pathname.startsWith(`${item.matchPrefix}/`)
  }
  return pathname === item.href
}
