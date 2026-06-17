export const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'https://your-school-domain.com/api/v1';

export const mobilePaths = {
  login: '/auth/token/',
  refresh: '/auth/token/refresh/',
  me: '/mobile/me/',
  dashboard: '/mobile/dashboard/',
  finance: '/mobile/finance/',
  paymentRequests: '/mobile/finance/payment-requests/',
  attendance: '/mobile/attendance/',
  exams: '/mobile/exams/',
  coursework: '/mobile/coursework/',
  messages: '/mobile/messages/',
  transport: '/mobile/transport/',
  registerDevice: '/mobile/devices/register/',
};
