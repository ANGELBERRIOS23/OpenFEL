export function getTheme(): 'dark' | 'light' {
  return (localStorage.getItem('openfel_theme') as 'dark' | 'light') || 'dark';
}

export function setTheme(t: 'dark' | 'light') {
  localStorage.setItem('openfel_theme', t);
  applyTheme(t);
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  setTheme(next);
  return next;
}

export function applyTheme(t?: 'dark' | 'light') {
  const theme = t || getTheme();
  document.body.className = theme;
}
