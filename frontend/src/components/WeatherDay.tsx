import type { ReactNode } from 'react'
import type { DayAirQuality, DayWeather, WeatherIcon } from '../lib/types'

const colors = {
  sun: '#FBBF24',
  sunOutline: '#D97706',
  cloud: '#DBEAFE',
  cloudOutline: '#64748B',
  stormCloud: '#94A3B8',
  rain: '#2563EB',
  snow: '#0284C7',
} as const
const cloudPath = 'M6 17h11a4 4 0 0 0 .6-8 6 6 0 0 0-11.4-1A4.5 4.5 0 0 0 6 17Z'
const cloud = <path d={cloudPath} fill={colors.cloud} stroke={colors.cloudOutline} />
const icons: Record<WeatherIcon, ReactNode> = {
  clear: <><circle cx="12" cy="12" r="4" fill={colors.sun} stroke={colors.sunOutline} /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5" stroke={colors.sunOutline} /></>,
  'partly-cloudy': <><circle cx="8" cy="8" r="3" fill={colors.sun} stroke={colors.sunOutline} /><path d="M8 1v2M1 8h2m.2-4.8 1.4 1.4M13 3l-1.4 1.4" stroke={colors.sunOutline} /><path d="M7 20h11a4 4 0 0 0 0-8 5 5 0 0 0-9.5 1A3.5 3.5 0 0 0 7 20Z" fill={colors.cloud} stroke={colors.cloudOutline} /></>,
  cloudy: cloud,
  fog: <><path d="M5 10h13a4 4 0 0 0-1-7 5 5 0 0 0-9 2 3 3 0 0 0-3 5Z" fill={colors.cloud} stroke={colors.cloudOutline} /><path d="M3 14h18M5 18h14M7 22h10" stroke={colors.cloudOutline} /></>,
  drizzle: <>{cloud}<path d="M7 20v1m5-1v1m5-1v1" stroke={colors.rain} /></>,
  rain: <>{cloud}<path d="m7 19-1 3m6-3-1 3m6-3-1 3" stroke={colors.rain} /></>,
  snow: <><path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3M9 20l3-3 3 3M4 11l4-1-1-4M20 13l-4 1 1 4M4 13l4 1-1 4M20 11l-4-1 1-4" stroke={colors.snow} /></>,
  thunderstorm: <><path d={cloudPath} fill={colors.stormCloud} stroke={colors.cloudOutline} /><path d="M13 14 9 19h4l-2 4 6-7h-4l1-2Z" fill={colors.sun} stroke={colors.sunOutline} /></>,
}

export default function WeatherDay({ weather, airQuality, airLoading = false, airStale = false, id }: {
  weather?: DayWeather | null; airQuality?: DayAirQuality; airLoading?: boolean; airStale?: boolean; id?: string
}) {
  if (!weather || !Object.prototype.hasOwnProperty.call(icons, weather.icon) || typeof weather.description !== 'string'
    || !Number.isFinite(weather.temperature_min) || !Number.isFinite(weather.temperature_max)) return null
  const humidity = typeof weather.humidity_mean === 'number' && Number.isFinite(weather.humidity_mean)
    && weather.humidity_mean >= 0 && weather.humidity_mean <= 100 ? weather.humidity_mean : null
  const air = airQuality && Number.isInteger(airQuality.aqi_max) && airQuality.aqi_max >= 0 ? airQuality : null
  const airText = air ? `${air.aqi_max}（${air.label}）${airStale ? '，缓存待更新' : ''}`
    : airLoading ? '加载中' : '暂无完整日预报'
  const label = `${weather.description}，最低 ${weather.temperature_min}°C，最高 ${weather.temperature_max}°C；日均相对湿度：${humidity === null ? '暂无' : humidity + '%'}；AQI（美标）日最高预报：${airText}。按杭州时间完整24小时预报计算。`
  return <span id={id} className="workhours-weather-day" title={label} role="img" aria-label={label}>
    <svg className="workhours-weather-icon" viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[weather.icon]}</svg>
    <span className="workhours-weather-readings">
      <span className="workhours-weather-temperature">{weather.temperature_min}°/{weather.temperature_max}°</span>
      <span className="workhours-weather-detail">湿度 {humidity === null ? '暂无' : Math.round(humidity) + '%'}</span>
      <span className="workhours-weather-detail">AQI(美) <strong className="workhours-weather-aqi" data-category={air?.category}>{air ? air.aqi_max : airLoading ? '…' : '暂无'}</strong></span>
    </span>
  </span>
}
