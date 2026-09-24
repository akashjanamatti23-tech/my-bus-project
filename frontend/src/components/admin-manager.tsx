import React, { useState } from 'react';
import { ScrollView, View, Text, Switch, RefreshControl } from 'react-native';
import { router } from 'expo-router';
import { colors } from '@/src/theme';
import { api } from '@/src/api';
import { useAuth } from '@/src/auth-context';
import { useResource } from '@/src/use-resource';
import { adminConfig } from '@/src/admin-config';
import { Header, IconButton, Icon, Button, Field, Select, Sheet, Card, Badge, Empty, Notice, Loading, s } from './ui';

export function AdminManager({ resource }: { resource: string }) {
  const config = adminConfig[resource];
  const { user } = useAuth();
  const { data, error, loading, refresh } = useResource<any[]>(`/admin/${resource}`, true);
  const buses = useResource<any[]>(resource === 'trips' ? '/admin/buses' : null);
  const routes = useResource<any[]>(resource === 'trips' ? '/admin/routes' : null);
  const staff = useResource<any[]>(resource === 'trips' ? '/admin/staff' : null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [values, setValues] = useState<any>(config.defaults);
  const [message, setMessage] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const begin = (item?: any) => {
    setEditing(item?.id || null); setMessage(''); setSuccess('');
    setValues(item ? Object.fromEntries(Object.keys(config.defaults).map(k => [k, Array.isArray(item[k]) ? item[k].join(', ') : item[k]])) : { ...config.defaults }); setOpen(true);
  };
  const save = async () => {
    setBusy(true); setMessage('');
    try {
      const body = { ...values };
      config.fields.forEach(field => { if (field.type === 'number') body[field.key] = Number(body[field.key]); });
      ['amenities', 'stops', 'boarding_points', 'dropping_points'].forEach(key => { if (key in body) body[key] = body[key].split(',').map((v: string) => v.trim()).filter(Boolean); });
      await api(`/admin/${resource}${editing ? `/${editing}` : ''}`, editing ? 'PUT' : 'POST', body);
      setOpen(false); setSuccess(`${config.singular[0].toUpperCase()}${config.singular.slice(1)} ${editing ? 'updated' : 'created'} successfully.`); await refresh();
    } catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  };
  const toggle = async (item: any) => {
    setMessage(''); setBusy(true);
    try { await api(`/admin/${resource}/${item.id}${resource === 'trips' ? '/publish' : ''}`, 'PATCH', resource === 'trips' ? { published: !item.published } : { active: !item.active }); await refresh(); }
    catch (e: any) { setMessage(e.message); } finally { setBusy(false); }
  };
  const options = (field: any) => field.key === 'bus_id' ? (buses.data || []).filter(b => b.active).map(b => ({ label: `${b.name} · ${b.number}`, value: b.id })) : field.key === 'route_id' ? (routes.data || []).filter(r => r.active).map(r => ({ label: `${r.source} → ${r.destination}`, value: r.id })) : field.key === 'driver_id' ? (staff.data || []).filter(d => d.role === 'driver' && d.active).map(d => ({ label: `${d.name} · ${d.driver_code}`, value: d.id })) : (field.options || []).filter((v: string) => field.key !== 'role' || user?.role === 'super_admin' || v === 'driver').map((v: string) => ({ label: v, value: v }));
  return <><Header title={config.title} subtitle={config.description} right={<IconButton name="add" testID={`add-${resource}-button`} onPress={() => begin()} />} /><ScrollView contentContainerStyle={s.content} refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} />}><Notice message={error || (!open ? message : '')} /><Notice message={success} success />{loading ? <Loading /> : !data?.length ? <Empty icon={config.icon} title={`Your ${resource === 'staff' ? 'team starts' : resource === 'buses' ? 'fleet starts' : 'network starts'} here`} description={resource === 'buses' ? 'Add your first bus, then build its exact physical seat and berth layout.' : resource === 'trips' ? 'Create a bus layout, route and driver first. Then bring them together in a published trip.' : `Create your first ${config.singular}. Every change is saved to your central GoBus workspace.`} action={<Button title={`Add ${config.singular}`} icon="add" testID={`create-first-${resource}-button`} onPress={() => begin()} />} /> : <><View style={s.between}><Text style={s.caption}>{data.length} {resource === 'staff' ? 'team members' : resource} in your network</Text><Button title={`Add ${config.singular}`} icon="add" secondary testID={`create-${resource}-button`} onPress={() => begin()} /></View>{data.map(item => <Card key={item.id} testID={`${resource}-record-${item.id}`}><View style={s.between}><View style={s.flex}><Text style={s.h2}>{resource === 'routes' ? `${item.source} → ${item.destination}` : resource === 'trips' ? `${item.route.source} → ${item.route.destination}` : resource === 'offers' ? item.title : item.name}</Text><Text style={s.caption}>{resource === 'buses' ? `${item.number} · ${item.operator}` : resource === 'routes' ? `${item.distance_km} km · ${item.duration_minutes} minutes` : resource === 'trips' ? `${item.date} · ${item.departure} IST` : resource === 'staff' ? `${item.role} · ${item.driver_code || item.email}` : item.code}</Text></View><Icon name={config.icon} /></View><View style={s.between}><Badge title={resource === 'trips' ? item.published ? 'PUBLISHED' : 'DRAFT' : item.active ? 'ACTIVE' : 'INACTIVE'} muted={resource === 'trips' ? !item.published : !item.active} />{resource === 'buses' && <Text style={s.caption}>{item.layout?.seats.filter((seat: any) => ['seat', 'berth'].includes(seat.type)).length || 0} seats configured</Text>}</View>{resource === 'buses' && <Button title="Open layout builder" testID={`edit-layout-${item.id}`} onPress={() => router.push({ pathname: '/admin/layout/[id]', params: { id: item.id } })} secondary />}{resource === 'trips' && <Text style={s.body}>{item.bus.number} · {item.driver_name}{'\n'}{item.status.replaceAll('_', ' ')}</Text>}{resource === 'staff' && <Text style={s.body}>{item.mobile}{item.license ? `\nLicense: ${item.license}` : ''}</Text>}{resource === 'routes' && <Text style={s.body}>{item.boarding_points.join(', ')} → {item.dropping_points.join(', ')}</Text>}<Button title={resource === 'trips' ? item.published ? 'Unpublish trip' : 'Publish trip' : resource === 'staff' ? item.active ? 'Disable account' : 'Enable account' : `Edit ${config.singular}`} testID={`edit-${resource}-${item.id}`} secondary disabled={busy} onPress={() => ['trips', 'staff'].includes(resource) ? toggle(item) : begin(item)} /></Card>)}</>}{error && <Button title="Try again" testID="retry-resource-button" onPress={refresh} />}</ScrollView><Sheet visible={open} onClose={() => setOpen(false)} title={`${editing ? 'Edit' : 'Add'} ${config.singular}`}><Notice message={message} />{resource === 'trips' && <Text style={s.body}>Only buses with saved layouts and a driver cabin can be scheduled. Dates and times use India Standard Time.</Text>}{config.fields.map(field => field.type === 'boolean' ? <View key={field.key} style={[s.between, { minHeight: 48 }]}><Text style={s.bodyStrong}>{field.label}</Text><Switch testID={`${resource}-${field.key}-input`} value={!!values[field.key]} onValueChange={v => setValues({ ...values, [field.key]: v })} trackColor={{ false: colors.surfaceTertiary, true: colors.brand }} thumbColor={colors.surface} /></View> : field.type === 'select' ? <Select key={field.key} label={field.label} testID={`${resource}-${field.key}-input`} value={values[field.key]} options={options(field)} onChange={v => setValues({ ...values, [field.key]: v })} /> : <Field key={field.key} label={field.label} testID={`${resource}-${field.key}-input`} value={String(values[field.key] ?? '')} onChangeText={v => setValues({ ...values, [field.key]: v })} keyboardType={field.type === 'number' ? 'number-pad' : field.key === 'email' ? 'email-address' : 'default'} secureTextEntry={field.type === 'password'} multiline={field.type === 'multiline'} placeholder={field.placeholder || field.label} />)}<Button title={`${editing ? 'Save' : 'Create'} ${config.singular}`} testID={`save-${resource}-button`} onPress={save} loading={busy} /></Sheet></>;
}