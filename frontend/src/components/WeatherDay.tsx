import type { ReactNode } from 'react'
import type { DayWeather, WeatherIcon } from '../lib/types'

const cloud = <path d="M6 17h11a4 4 0 0 0 .6-8 6 6 0 0 0-11.4-1A4.5 4.5 0 0 0 6 17Z" />
const icons: Record<WeatherIcon, ReactNode> = {
  clear: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4 19 5" /></>,
  'partly-cloudy': <><circle cx="8" cy="8" r="3" /><path d="M8 1v2M1 8h2m.2-4.8 1.4 1.4M13 3l-1.4 1.4" /><path d="M7 20h11a4 4 0 0 0 0-8 5 5 0 0 0-9.5 1A3.5 3.5 0 0 0 7 20Z" /></>,
  cloudy: cloud,
  fog: <><path d="M5 10h13a4 4 0 0 0-1-7 5 5 0 0 0-9 2 3 3 0 0 0-3 5Z" /><path d="M3 14h18M5 18h14M7 22h10" /></>,
  drizzle: <>{cloud}<path d="M7 20v1m5-1v1m5-1v1" /></>,
  rain: <>{cloud}<path d="m7 19-1 3m6-3-1 3m6-3-1 3" /></>,
  snow: <><path d="M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3M9 20l3-3 3 3M4 11l4-1-1-4M20 13l-4 1 1 4M4 13l4 1-1 4M20 11l-4-1 1-4" /></>,
  thunderstorm: <>{cloud}<path d="m13 15-4 5h4l-2 4" /></>,
}

export default function WeatherDay({ weather }: { weather?: DayWeather | null }) {
  if (!weather || !Object.prototype.hasOwnProperty.call(icons, weather.icon) || typeof weather.description !== 'string'
    || !Number.isFinite(weather.temperature_min) || !Number.isFinite(weather.temperature_max)) return null
  const label = `${weather.description}，最低 ${weather.temperature_min}°C，最高 ${weather.temperature_max}°C`
  return <span className="workhours-weather-day" title={label} role="img" aria-label={label}>
    <svg className="workhours-weather-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{icons[weather.icon]}</svg>
    <span className="workhours-weather-temperature">{weather.temperature_min}°/{weather.temperature_max}°</span>
  </span>
}
