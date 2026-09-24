import app from './app.json';
export default {
  ...app.expo,
  name: 'GoBus',
  slug: 'gobus',
  scheme: 'gobus',
  userInterfaceStyle: 'light',
  extra: { backendUrl: process.env.EXPO_PUBLIC_BACKEND_URL },
};