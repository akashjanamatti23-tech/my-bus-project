import React, { useState } from 'react';
import { ScrollView, Text, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { api } from '@/src/api';
import { useAuth } from '@/src/auth-context';
import { useResource } from '@/src/use-resource';
import { SeatMap, LayoutSeat } from '@/src/components/seat-map';
import { Screen, Header, Button, Loading, Notice, money, s } from '@/src/components/ui';

export default function Seats() {
  const { id, count = '1' } = useLocalSearchParams<{ id: string; count?: string }>();
  const { user } = useAuth();
  const { data: trip, loading, error, refresh } = useResource(`/trips/${id}`, true);
  const [selected, setSelected] = useState<string[]>([]); const [message, setMessage] = useState(''); const [busy, setBusy] = useState(false);
  const selectedSeats: LayoutSeat[] = trip?.layout.seats.filter((s: LayoutSeat) => selected.includes(s.id)) || [];
  const select = (seat: LayoutSeat) => { setMessage(''); if (selected.includes(seat.id)) setSelected(selected.filter(s => s !== seat.id)); else if (selected.length < Number(count)) setSelected([...selected, seat.id]); else setMessage(`You can select ${count} seat(s) for this search.`); };
  const proceed = async () => {
    if (!user) { router.push('/sign-in'); return; }
    setBusy(true); setMessage('');
    try { const hold = await api(`/trips/${id}/holds`, 'POST', { seat_ids: selected }); router.push({ pathname: '/passenger-details', params: { id, hold: hold.id, seats: selected.join(','), expires: hold.expires_at } }); }
    catch (e: any) { setMessage(e.message); await refresh(); } finally { setBusy(false); }
  };
  return <Screen><Header title="Pick your place" subtitle={`Select ${count} seat${count === '1' ? '' : 's'} · fares set by the operator`} back /><ScrollView contentContainerStyle={s.content}><Notice message={error || message} />{loading ? <Loading /> : trip && <><Text style={s.body}>Every bus is different. This is the exact layout configured for your journey. L indicates a ladies-reserved seat.</Text><SeatMap layout={trip.layout} states={trip.seat_states} selected={selected} onSeat={select} /></>}{error && <Button title="Refresh seats" testID="refresh-seats-button" onPress={refresh} />}</ScrollView><View style={s.footer}><View style={s.between}><View style={s.flex}><Text style={s.caption}>YOUR SEATS</Text><Text testID="selected-seats-label" style={s.bodyStrong}>{selectedSeats.map(s => s.label).join(', ') || 'Choose a little room for you'}</Text></View><Text testID="selected-seats-total" style={s.h2}>{money(selectedSeats.reduce((sum, s) => sum + s.price, 0))}</Text></View><Button title={user ? 'Continue with these seats' : 'Sign in to continue'} testID="hold-seats-button" onPress={proceed} loading={busy} disabled={selected.length !== Number(count)} /><Text style={[s.caption, s.center]}>Continue holds your seats for 5 minutes. No payment taken.</Text></View></Screen>;
}