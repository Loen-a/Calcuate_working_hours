import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import WeatherDay from './WeatherDay'

const weather = { code: 61, description: '小雨', icon: 'rain' as const, temperature_min: 20.1, temperature_max: 27.6, humidity_mean: 72.4 }

it('explains daily humidity and complete-day US AQI in the hover and accessible descriptions', () => {
  render(<WeatherDay weather={weather} airQuality={{ aqi_max: 86, category: 'moderate', label: '中等' }} airStale />)
  const icon = screen.getByRole('img')
  expect(icon).toHaveAccessibleName(/日均相对湿度：72.4%.*AQI（美标）日最高预报：86（中等），缓存待更新.*完整24小时/)
  expect(icon).toHaveAttribute('title', icon.getAttribute('aria-label'))
  expect(screen.getByText('湿度 72%')).toBeInTheDocument()
  expect(screen.getByText('86')).toHaveAttribute('data-category', 'moderate')
})

it('keeps a real zero but never invents humidity or AQI when missing', () => {
  const { rerender } = render(<WeatherDay weather={{ ...weather, humidity_mean: 0 }} airQuality={{ aqi_max: 0, category: 'good', label: '良好' }} />)
  expect(screen.getByText('湿度 0%')).toBeInTheDocument()
  expect(screen.getByRole('img')).toHaveAccessibleName(/日最高预报：0（良好）/)
  rerender(<WeatherDay weather={{ ...weather, humidity_mean: undefined }} />)
  expect(screen.getByRole('img')).toHaveAccessibleName(/日均相对湿度：暂无.*暂无完整日预报/)
  expect(screen.queryByText('0')).not.toBeInTheDocument()
})
