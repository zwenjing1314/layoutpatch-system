export type Theme = 'dark' | 'light';
export const THEME_KEY = 'layoutpatch-theme';
export const THEME_BOOTSTRAP = `(()=>{let t='dark';try{const v=localStorage.getItem('layoutpatch-theme');if(v==='light'||v==='dark')t=v}catch{}document.documentElement.dataset.theme=t})()`;

const listeners = new Set<() => void>();
export function currentTheme(): Theme {
  return typeof document !== 'undefined' && document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}
export function serverTheme(): Theme { return 'dark'; }
function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  listeners.forEach(listener => listener());
}
export function changeTheme(theme: Theme) {
  apply(theme);
  try { window.localStorage.setItem(THEME_KEY, theme); } catch { /* The current page still works without storage. */ }
}
function storageChanged(event: StorageEvent) {
  if (event.key !== THEME_KEY && event.key !== null) return;
  if (event.newValue === 'light' || event.newValue === 'dark' || event.newValue === null) apply(event.newValue === 'light' ? 'light' : 'dark');
}
export function subscribeTheme(listener: () => void) {
  if (listeners.size === 0) window.addEventListener('storage', storageChanged);
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) window.removeEventListener('storage', storageChanged);
  };
}
