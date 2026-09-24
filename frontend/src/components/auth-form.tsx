import React, { useState } from 'react';
import { ScrollView, Text, View, StyleSheet, Pressable } from 'react-native';
import { router } from 'expo-router';
import { api } from '@/src/api';
import { useAuth } from '@/src/auth-context';
import { colors, fonts } from '@/src/theme';
import { Screen, Header, Field, Button, Notice, Icon, s } from './ui';

export function AuthForm({ portal = 'passenger' }: { portal?: 'passenger' | 'admin' | 'driver' }) {
  const { accept } = useAuth();
  const [register, setRegister] = useState(false);
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [mobile, setMobile] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true); setError('');
    try {
      const result = await api(register ? '/auth/register' : '/auth/login', 'POST', register ? { name, email: identifier, mobile, password } : { identifier, password, portal });
      await accept(result);
      router.replace(portal === 'admin' ? '/admin' : portal === 'driver' ? '/driver' : '/(passenger)/home');
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  };
  return <Screen><Header title="" back /><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled"><View style={styles.logo}><Icon name={portal === 'admin' ? 'grid-outline' : portal === 'driver' ? 'speedometer-outline' : 'bus-outline'} size={34} color={colors.onBrand} /></View><Text style={styles.wordmark}>GoBus<Text style={{ color: colors.brandSecondary }}>.</Text></Text><Text style={s.overline}>{portal === 'admin' ? 'OPERATIONS WORKSPACE' : portal === 'driver' ? 'DRIVER / IN-BUS' : 'YOUR NEXT JOURNEY STARTS HERE'}</Text><View style={{ gap: 8, marginVertical: 10 }}><Text style={s.h1}>{register ? 'Let’s get you going.' : portal === 'passenger' ? 'Welcome aboard.' : 'Welcome back.'}</Text><Text style={s.body}>{register ? 'Create your passenger account in a few simple steps.' : portal === 'admin' ? 'Sign in to manage the GoBus ecosystem.' : portal === 'driver' ? 'Your assigned trips. One focused workspace.' : 'Sign in for a more connected journey.'}</Text></View><Notice message={error} />{register && <Field label="Full name" testID="register-name-input" value={name} onChangeText={setName} autoCapitalize="words" placeholder="Your full name" />}<Field label={register ? 'Email address' : portal === 'driver' ? 'Driver ID or mobile / email' : 'Email or mobile number'} testID="login-identifier-input" value={identifier} onChangeText={setIdentifier} keyboardType={register ? 'email-address' : 'default'} placeholder={register ? 'you@example.com' : 'Enter email or mobile'} />{register && <Field label="Mobile number" testID="register-mobile-input" value={mobile} onChangeText={setMobile} placeholder="10-digit mobile number" keyboardType="phone-pad" />}<Field label={register ? 'Password · at least 12 characters' : 'Password'} testID="login-password-input" value={password} onChangeText={setPassword} placeholder="Enter your password" secureTextEntry /><Button title={register ? 'Create passenger account' : 'Sign in'} icon="arrow-forward" testID="login-submit-button" onPress={submit} loading={busy} />{portal === 'passenger' && <Pressable testID="toggle-registration-button" onPress={() => { setRegister(!register); setError(''); }} style={styles.switch}><Text style={s.body}>{register ? 'Already have an account? ' : 'New to GoBus? '}<Text style={s.link}>{register ? 'Sign in' : 'Create an account'}</Text></Text></Pressable>}<View style={styles.security}><Icon name="shield-checkmark-outline" size={17} /><Text style={s.caption}>Secure sign-in. Your account stays yours.</Text></View>{portal !== 'passenger' && <Text style={[s.caption, s.center]}>Access is provided by your GoBus administrator.{portal === 'driver' ? '\nDrivers can only access their assigned trips.' : ''}</Text>}</ScrollView></Screen>;
}
const styles = StyleSheet.create({ content: { padding: 26, gap: 17, paddingBottom: 40, maxWidth: 520, width: '100%', alignSelf: 'center' }, logo: { width: 66, height: 66, backgroundColor: colors.brand, borderRadius: 22, alignItems: 'center', justifyContent: 'center' }, wordmark: { fontFamily: fonts.heading, color: colors.onSurface, fontSize: 32, fontWeight: '800', letterSpacing: -1.5 }, switch: { minHeight: 48, alignItems: 'center', justifyContent: 'center' }, security: { flexDirection: 'row', gap: 8, justifyContent: 'center', alignItems: 'center', marginTop: 20 } });