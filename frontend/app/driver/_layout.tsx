import { Slot, Redirect } from 'expo-router';
import { useAuth } from '@/src/auth-context';
import { Loading } from '@/src/components/ui';
export default function DriverLayout() { const { user, loading } = useAuth(); if (loading) return <Loading />; if (!user || user.role !== 'driver') return <Redirect href="/driver-login" />; return <Slot />; }