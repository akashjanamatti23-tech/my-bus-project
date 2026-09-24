import React, { useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View, KeyboardAvoidingView, Platform, TextInputProps, ColorValue } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { colors, fonts } from '@/src/theme';

export function Icon({ name, size = 22, color = colors.brand }: { name: any; size?: number; color?: ColorValue }) { return <Ionicons name={name in Ionicons.glyphMap ? name : 'arrow-forward-outline'} size={size} color={color} />; }
export function Button({ title, onPress, testID, secondary = false, loading = false, disabled = false, icon }: { title: string; onPress: () => void; testID: string; secondary?: boolean; loading?: boolean; disabled?: boolean; icon?: string }) {
  return <Pressable accessibilityRole="button" accessibilityLabel={title} testID={testID} onPress={onPress} disabled={disabled || loading} style={({ pressed }) => [s.button, secondary && s.secondary, (disabled || loading) && s.disabled, pressed && s.pressed]}>{loading ? <ActivityIndicator color={secondary ? colors.brand : colors.onBrand} /> : <>{icon && <Icon name={icon} color={secondary ? colors.brand : colors.onBrand} size={19} />}<Text style={[s.buttonText, secondary && { color: colors.brand }]}>{title}</Text></>}</Pressable>;
}
export function IconButton({ name, onPress, testID, label }: { name: string; onPress: () => void; testID: string; label?: string }) { return <Pressable accessibilityRole="button" accessibilityLabel={label || name} testID={testID} onPress={onPress} style={({ pressed }) => [s.iconButton, pressed && s.pressed]}><Icon name={name} color={colors.onSurface} /></Pressable>; }
export function Header({ title, subtitle, back = false, right }: { title: string; subtitle?: string; back?: boolean; right?: React.ReactNode }) {
  return <View style={s.header} testID="screen-header">{back && <IconButton name="arrow-back" testID="navigate-back-button" onPress={() => router.canGoBack() ? router.back() : router.replace('/')} />}<View style={s.flex}><Text numberOfLines={1} testID="screen-title" style={s.headerTitle}>{title}</Text>{subtitle && <Text style={s.caption}>{subtitle}</Text>}</View>{right}</View>;
}
export function Screen({ children, bottom = true }: { children: React.ReactNode; bottom?: boolean }) { return <SafeAreaView edges={bottom ? ['top', 'bottom'] : ['top']} style={s.screen}><KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.flex}>{children}</KeyboardAvoidingView></SafeAreaView>; }
export function Card({ children, testID }: { children: React.ReactNode; testID?: string }) { return <View testID={testID} style={s.card}>{children}</View>; }
export function Field({ label, testID, ...props }: TextInputProps & { label: string; testID: string }) { return <View style={s.field}><Text style={s.label}>{label}</Text><TextInput testID={testID} placeholderTextColor={colors.muted} autoCapitalize="none" style={[s.input, props.multiline && { minHeight: 100, textAlignVertical: 'top' }]} {...props} /></View>; }
export function Notice({ message, success = false }: { message?: string; success?: boolean }) { if (!message) return null; return <View testID={success ? 'success-message' : 'error-message'} accessibilityRole="alert" style={[s.notice, success && { borderColor: colors.brandTertiary }]}><Icon name={success ? 'checkmark-circle-outline' : 'information-circle-outline'} color={success ? colors.brand : colors.error} size={20} /><Text style={[s.noticeText, success && { color: colors.brand }]}>{message}</Text></View>; }
export function Empty({ icon = 'bus-outline', title, description, action }: { icon?: string; title: string; description: string; action?: React.ReactNode }) { return <View testID="empty-state" style={s.empty}><View style={s.emptyIcon}><Icon name={icon} size={30} /></View><Text style={s.h2}>{title}</Text><Text style={[s.body, s.center]}>{description}</Text>{action}</View>; }
export function Loading() { return <View style={s.empty} testID="loading-state"><ActivityIndicator size="large" color={colors.brand} /></View>; }
export function Badge({ title, muted = false }: { title: string; muted?: boolean }) { return <View style={[s.badge, muted && { backgroundColor: colors.surfaceSecondary }]}><Text testID="status-label" style={[s.badgeText, muted && { color: colors.muted }]}>{title.replaceAll('_', ' ')}</Text></View>; }
export function Section({ title, action, onPress }: { title: string; action?: string; onPress?: () => void }) { return <View style={s.section}><Text style={s.h2}>{title}</Text>{action && <Pressable testID={`${action.toLowerCase().replaceAll(' ', '-')}-button`} onPress={onPress} style={s.smallAction}><Text style={s.link}>{action}</Text><Icon name="arrow-forward" size={16} /></Pressable>}</View>; }
export function Sheet({ visible, onClose, title, children }: { visible: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={s.modal}>
        <Pressable testID="sheet-dismiss-overlay" style={StyleSheet.absoluteFill} onPress={onClose} />
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={[s.sheet, { paddingBottom: Math.max(insets.bottom, 16) }]}>
          <View style={s.handle} />
          <Header title={title} right={<IconButton name="close" testID="close-sheet-button" onPress={onClose} />} />
          <ScrollView testID="sheet-content-scroll" style={s.sheetScroll} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={s.content}>
            {children}
          </ScrollView>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
export function Select({ label, value, options, onChange, testID, placeholder = 'Select an option' }: { label: string; value: string; options: { label: string; value: string }[]; onChange: (value: string) => void; testID: string; placeholder?: string }) {
  const [open, setOpen] = useState(false);
  return <View style={s.field}><Text style={s.label}>{label}</Text><Pressable testID={testID} accessibilityRole="button" onPress={() => setOpen(true)} style={s.select}><Text style={[s.selectText, !value && { color: colors.muted }]}>{options.find(o => o.value === value)?.label || placeholder}</Text><Icon name="chevron-down" size={18} /></Pressable><Sheet visible={open} onClose={() => setOpen(false)} title={label}>{options.length ? options.map((option, i) => <Pressable key={option.value} testID={`${testID}-option-${i}`} accessibilityRole="button" onPress={() => { onChange(option.value); setOpen(false); }} style={s.option}><Text style={s.bodyStrong}>{option.label}</Text>{value === option.value && <Icon name="checkmark-circle" />}</Pressable>) : <Empty title="Nothing to select yet" description="Options will appear once configured by GoBus operations." />}</Sheet></View>;
}
export function Chips({ values, value, onChange, testID }: { values: string[]; value: string; onChange: (v: string) => void; testID: string }) {
  return <View style={s.chipRow}><ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipContent}>{values.map((v, i) => <Pressable key={v} testID={`${testID}-${i}`} onPress={() => onChange(v)} style={[s.chip, value === v && s.chipActive]}><Text style={[s.chipText, value === v && { color: colors.onBrand }]}>{v}</Text></Pressable>)}</ScrollView></View>;
}
export const money = (value: number) => `₹${value.toLocaleString('en-IN')}`;
export const s = StyleSheet.create({
  flex: { flex: 1 }, screen: { flex: 1, backgroundColor: colors.canvas }, content: { padding: 20, gap: 18, paddingBottom: 32 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, minHeight: 76, backgroundColor: colors.glass },
  headerTitle: { fontFamily: fonts.heading, fontSize: 23, fontWeight: '700', color: colors.onSurface, letterSpacing: -0.8 },
  h1: { fontFamily: fonts.heading, fontSize: 32, lineHeight: 41, fontWeight: '700', color: colors.onSurface, letterSpacing: -1.2 },
  h2: { fontFamily: fonts.heading, fontSize: 19, fontWeight: '700', color: colors.onSurface, letterSpacing: -0.5 },
  body: { fontFamily: fonts.body, fontSize: 14, lineHeight: 22, color: colors.muted }, bodyStrong: { fontFamily: fonts.body, fontSize: 14, lineHeight: 22, color: colors.onSurface, fontWeight: '600' },
  caption: { fontFamily: fonts.body, fontSize: 11, lineHeight: 18, color: colors.muted }, overline: { fontFamily: fonts.body, fontSize: 10, fontWeight: '700', letterSpacing: 1.5, color: colors.muted },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 }, between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  card: { borderRadius: 20, padding: 20, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, gap: 16, overflow: 'hidden' },
  button: { minHeight: 54, borderRadius: 14, backgroundColor: colors.brand, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 10, paddingHorizontal: 18 },
  secondary: { backgroundColor: colors.brandTertiary }, buttonText: { fontFamily: fonts.body, color: colors.onBrand, fontSize: 14, fontWeight: '700' },
  disabled: { opacity: 0.45 }, pressed: { opacity: 0.68, transform: [{ scale: 0.985 }] },
  iconButton: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 22, backgroundColor: colors.surface },
  field: { gap: 8 }, label: { fontFamily: fonts.body, fontSize: 12, color: colors.onSurfaceSecondary, fontWeight: '600' },
  input: { height: 52, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, fontFamily: fonts.body, fontSize: 14, color: colors.onSurface, backgroundColor: colors.surface },
  select: { minHeight: 52, borderWidth: 1, borderColor: colors.border, borderRadius: 12, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: colors.surface },
  selectText: { flex: 1, fontFamily: fonts.body, fontSize: 14, color: colors.onSurface },
  notice: { padding: 12, borderWidth: 1, borderColor: colors.error, borderRadius: 12, flexDirection: 'row', gap: 8, backgroundColor: colors.surface },
  noticeText: { color: colors.error, fontSize: 12, lineHeight: 19, fontFamily: fonts.body, flex: 1 },
  empty: { alignItems: 'center', paddingHorizontal: 24, paddingVertical: 36, gap: 14 }, emptyIcon: { width: 68, height: 68, borderRadius: 24, backgroundColor: colors.brandTertiary, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
  center: { textAlign: 'center' }, badge: { alignSelf: 'flex-start', backgroundColor: colors.brandTertiary, paddingVertical: 5, paddingHorizontal: 9, borderRadius: 6 }, badgeText: { fontSize: 10, fontFamily: fonts.body, fontWeight: '700', color: colors.brand },
  section: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 }, smallAction: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 44 }, link: { fontFamily: fonts.body, color: colors.brand, fontWeight: '700', fontSize: 12 },
  modal: { flex: 1, backgroundColor: colors.overlay, justifyContent: 'flex-end' }, sheet: { backgroundColor: colors.canvas, borderTopLeftRadius: 28, borderTopRightRadius: 28, height: '86%', flexShrink: 0, overflow: 'hidden' }, sheetScroll: { flex: 1, minHeight: 0 },
  handle: { width: 36, height: 4, backgroundColor: colors.borderStrong, borderRadius: 2, alignSelf: 'center', marginTop: 12 },
  option: { minHeight: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderColor: colors.border, paddingVertical: 12 },
  chipRow: { height: 56, flexShrink: 0, backgroundColor: colors.canvas }, chipContent: { alignItems: 'center', paddingHorizontal: 20, gap: 8 },
  chip: { flexShrink: 0, height: 36, paddingHorizontal: 15, borderRadius: 18, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, justifyContent: 'center' }, chipActive: { backgroundColor: colors.brand, borderColor: colors.brand }, chipText: { fontFamily: fonts.body, fontSize: 12, fontWeight: '600', color: colors.onSurfaceSecondary },
  footer: { padding: 20, gap: 12, borderTopWidth: 1, borderColor: colors.border, backgroundColor: colors.glass }, divider: { height: 1, backgroundColor: colors.border },
});