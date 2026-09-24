import { Tabs, Redirect } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Icon, Loading } from '@/src/components/ui';
import { colors, fonts } from '@/src/theme';
import { useAuth } from '@/src/auth-context';

export default function PassengerLayout() {
  const { user, loading } = useAuth();
  const insets = useSafeAreaInsets();
  if (loading) return <Loading />;
  if (user && user.role !== 'passenger') return <Redirect href={user.role === 'driver' ? '/driver' : '/admin'} />;
  return <Tabs screenOptions={{ headerShown: false, tabBarActiveTintColor: colors.brand, tabBarInactiveTintColor: colors.muted, tabBarStyle: { backgroundColor: colors.glass, borderTopColor: colors.border, height: 68 + insets.bottom, paddingBottom: Math.max(insets.bottom, 8), paddingTop: 8 }, tabBarLabelStyle: { fontFamily: fonts.body, fontSize: 10, fontWeight: '600', marginTop: 3 }, sceneStyle: { backgroundColor: colors.canvas } }}>
    {[['home', 'Home', 'home-outline'], ['search', 'Search', 'search-outline'], ['bookings', 'My bookings', 'ticket-outline'], ['offers', 'Offers', 'pricetag-outline'], ['profile', 'Profile', 'person-outline']].map(([name, title, icon]) => <Tabs.Screen key={name} name={name} options={{ title, tabBarButtonTestID: `${name}-tab`, tabBarIcon: ({ color }) => <Icon name={icon} color={color} size={22} /> }} />)}
  </Tabs>;
}