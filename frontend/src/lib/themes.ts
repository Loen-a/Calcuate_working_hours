import type { Theme } from './types'

export const THEMES: ReadonlyArray<{ id: Theme; label: string; colors: readonly string[] }> = [
  { id: 'cool', label: '冷色', colors: ['#F7F9FC', '#2A4A6B', '#7A3A4E', '#8A6E1E'] },
  { id: 'teal', label: '青绿', colors: ['#F6FAF8', '#2D6B5F', '#B36B5E', '#B0893D'] },
  { id: 'classic', label: '经典绿', colors: ['#F5F7F4', '#116B5C', '#B42318', '#B56B16'] },
  { id: 'candy', label: '晴空糖果', colors: ['#EDF6FF', '#4564D6', '#FF9DB3', '#FFD778'] },
  { id: 'space', label: '星际软糖', colors: ['#10162B', '#75E2ED', '#FFA6C9', '#B5A5FF'] },
  { id: 'journal', label: '奶油手账', colors: ['#FFF8EA', '#47765F', '#E7AC8B', '#E9D58F'] },
]
