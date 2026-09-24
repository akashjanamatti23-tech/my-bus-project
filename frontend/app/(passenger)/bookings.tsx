import { useState } from 'react';
import { ScrollView, Text } from 'react-native';
import { router } from 'expo-router';
import { useAuth } from '@/src/auth-context';
import { useResource } from '@/src/use-resource';
import { Screen, Header, Chips, Card, Badge, Empty, Button, Loading, Notice, s } from '@/src/components/ui';

export default function Bookings() {
  const { user } = useAuth();
  const { data, error, loading, refresh } = useResource<any[]>(user ? '/bookings' : null, true);
  const [category, setCategory] = useState('Upcoming');
  const filtered = (data || []).filter(booking => category === 'Completed' ? booking.journey_status === 'COMPLETED' : category === 'Cancelled' ? booking.status === 'CANCELLED' : category === 'Ongoing' ? ['JOURNEY_STARTED', 'IN_TRANSIT'].includes(booking.journey_status) : ['CONFIRMED', 'UPCOMING'].includes(booking.status));
  return <Screen bottom={false}><Header title="Your journeys" subtitle="Every ticket. Every memory. In one place." /><Chips values={['Upcoming', 'Ongoing', 'Completed', 'Cancelled']} value={category} onChange={setCategory} testID="booking-category" /><ScrollView contentContainerStyle={s.content}><Notice message={error} />{!user ? <Empty icon="ticket-outline" title="Your next chapter awaits" description="Sign in to see your bookings and keep your journeys together." action={<Button title="Sign in" testID="bookings-sign-in-button" onPress={() => router.push('/sign-in')} />} /> : loading ? <Loading /> : filtered.length ? filtered.map(booking => <Card key={booking.id} testID={`booking-${booking.id}`}><Badge title={booking.status} /><Text style={s.h2}>{booking.pnr}</Text><Text style={s.body}>{booking.id}</Text></Card>) : <Empty icon="ticket-outline" title={`No ${category.toLowerCase()} journeys yet`} description="Your confirmed bookings will appear here. A seat hold is not a confirmed booking." action={<Button title="Find a journey" testID="bookings-find-journey-button" secondary onPress={() => router.push('/(passenger)/home')} />} />}{error && <Button title="Try again" testID="retry-bookings-button" onPress={refresh} />}</ScrollView></Screen>;
}