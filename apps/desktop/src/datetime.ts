// FastAPI 的历史 naive 时间戳按后端约定为 UTC；浏览器不能将它当作本地时间。
export function apiDate(value: string): Date {
  const timestamp = value.replace(' ', 'T');
  const hasTime = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(timestamp);
  const hasOffset = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
  return new Date(hasTime && !hasOffset ? `${timestamp}Z` : timestamp);
}
