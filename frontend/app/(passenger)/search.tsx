import React, { useState } from 'react';
import { ScrollView, Text, View, RefreshControl } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { format } from 'date-fns';
import { Screen, Header, Chips, Empty, Loading, Notice, Button, IconButton, s } from '@/src/components/ui';
import { SearchForm } from '@/src/components/search-form';
import { TripCard } from '@/src/components/trip-card';
import { useResource } from '@/src/use-resource';

export default function Search() {
  const params = useLocalSearchParams<{ source?: string; destination?: string; date?: string; count?: string }>();
  const [search, setSearch] = useState<any>(null);
  const [edit, setEdit] = useState(false);
  const [filter, setFilter] = useState('All buses');
  const [sort, setSort] = useState('Departure');
  const criteria = search || params;
  const hasSearch = !!criteria.source && !!criteria.destination;
  const date = criteria.date || format(new Date(), 'yyyy-MM-dd');
  const path = hasSearch ? `/trips?source=${encodeURIComponent(criteria.source)}&destination=${encodeURIComponent(criteria.destination)}&journey_date=${date}&passengers=${criteria.count || 1}&sort=${sort.toLowerCase()}${filter === 'AC' ? '&ac=true' : filter === 'Non-AC' ? '&ac=false' : filter === 'Sleeper' || filter === 'Seater' ? `&bus_type=${filter}` : ''}` : null;
  const { data, loading, error, refresh } = useResource<any[]>(path, true);
  return <Screen bottom={false}><Header title={hasSearch ? `${criteria.source} → ${criteria.destination}` : 'Find your next journey'} subtitle={hasSearch ? `${date} · ${criteria.count || 1} traveller(s)` : 'A new destination is just a search away.'} right={hasSearch ? <IconButton name={edit ? 'close' : 'options-outline'} testID="edit-search-button" onPress={() => setEdit(!edit)} /> : undefined} />{hasSearch && !edit && <Chips values={['All buses', 'AC', 'Non-AC', 'Sleeper', 'Seater']} value={filter} onChange={setFilter} testID="bus-filter" />}<ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled" refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} />}>{!hasSearch || edit ? <SearchForm initialSource={criteria.source} initialDestination={criteria.destination} onSearch={p => { setSearch(p); setEdit(false); }} /> : <><View style={s.between}><Text testID="bus-results-count" style={s.caption}>{data?.length || 0} buses found</Text><Button title={sort === 'Price' ? 'Lowest price' : 'Departure time'} testID="sort-results-button" secondary onPress={() => setSort(sort === 'Price' ? 'Departure' : 'Price')} /></View><Notice message={error} />{loading ? <Loading /> : data?.length ? data.map(trip => <TripCard key={trip.id} trip={trip} count={criteria.count || '1'} />) : <Empty title="A different route, perhaps?" description="No published buses match this journey yet. Try another date or route." action={<Button title="Change search" testID="change-empty-search-button" onPress={() => setEdit(true)} secondary />} />}{error && <Button title="Try again" testID="retry-search-button" onPress={refresh} />}</>}</ScrollView></Screen>;
}