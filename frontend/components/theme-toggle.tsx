"use client";
import { useSyncExternalStore } from 'react';
import { changeTheme, currentTheme, serverTheme, subscribeTheme } from '@/lib/theme';

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme, serverTheme);
  return <button type="button" className="theme-toggle" aria-label={theme === 'dark' ? '切换到白色主题' : '切换到深色主题'}
    onClick={() => changeTheme(theme === 'dark' ? 'light' : 'dark')}>
    <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span><span>{theme === 'dark' ? '白色主题' : '深色主题'}</span>
  </button>;
}
