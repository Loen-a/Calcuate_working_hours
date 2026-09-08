export type Theme = 'cool' | 'teal'
export type Period = 'week' | 'month'
export type CalendarKind = 'holiday' | 'workday'
export interface Entry { start_time: string | null; end_time: string | null }
export interface Interval {
  interval_id: number
  name: string
  start_time: string
  end_time: string
  enabled: boolean
}
export interface Day {
  date: string
  is_workday: boolean
  leave: boolean
  calendar_name: string
  manual_override: CalendarKind | null
  entry: Entry | null
  actual_minutes: number | null
  daily_balance_minutes: number | null
  cumulative_balance_minutes: number | null
  balance_before_minutes: number
  required_minutes: number | null
  recommended_minutes: number | null
  suggested_end: string | null
  suggested_end_day_offset: number | null
  reason: string
  compliant: boolean | null
}
export interface Preview {
  available: boolean
  required_minutes?: number
  required_label?: string
  balance_before_minutes?: number
  balance_label?: string
  reason_label?: string
  suggested_end?: string | null
  suggested_end_label?: string
  day_offset?: number | null
}
export interface DashboardData {
  today: string
  selected_date: string
  theme: Theme
  settings: { period: Period; target_minutes_per_day: number; minimum_minutes_per_day: number }
  intervals: Interval[]
  days: Day[]
  selected_preview: Preview
  month: {
    start: string; end: string; target_minutes: number; completed_minutes: number
    balance_minutes: number; remaining_target_minutes: number; workday_count: number
    recorded_days: number; missing_history_days: string[]
  }
  forecast: {
    period_start: string; period_end: string; target_minutes: number; completed_minutes: number
    remaining_target_minutes: number; carryover_minutes: number; goal_met: boolean
  }
  holiday_status: { year: number; source: 'cache' | 'remote' | 'fallback'; warning: string | null }
}
