import React, { useState } from 'react';
import { ScrollView, Text, RefreshControl } from 'react-native';
import { api } from '@/src/api';
import { useResource } from '@/src/use-resource';
import { Header, Card, Badge, Button, Sheet, Field, Select, Empty, Loading, Notice, s } from '@/src/components/ui';

export default function SupportInbox() {
  const { data, error, loading, refresh } = useResource<any[]>('/admin/support', true);
  const [ticket, setTicket] = useState<any>(null);
  const [reply, setReply] = useState('');
  const [status, setStatus] = useState('IN_PROGRESS');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true); setMessage('');
    try {
      await api(`/admin/support/${ticket.id}`, 'PATCH', { reply, status });
      setTicket(null); await refresh();
    } catch (e: any) { setMessage(e.message); }
    finally { setBusy(false); }
  };
  return <>
    <Header title="Support inbox" subtitle="Be there for every traveller and driver." />
    <ScrollView contentContainerStyle={s.content} refreshControl={<RefreshControl refreshing={false} onRefresh={refresh} />}>
      <Notice message={error} />
      {loading ? <Loading /> : data?.length ? data.map(item => (
        <Card key={item.id} testID={`support-ticket-${item.id}`}>
          <Badge title={item.status} />
          <Text style={s.h2}>{item.subject}</Text>
          <Text style={s.body}>{item.message}</Text>
          <Text style={s.caption}>{item.name} · {new Date(item.created_at).toLocaleString('en-IN')}</Text>
          {Boolean(item.reply) && <Text style={s.bodyStrong}>Your reply: {item.reply}</Text>}
          <Button title="Reply & update" testID={`reply-ticket-${item.id}`} secondary onPress={() => {
            setTicket(item); setReply(item.reply || ''); setStatus(item.status === 'OPEN' ? 'IN_PROGRESS' : item.status); setMessage('');
          }} />
        </Card>
      )) : <Empty icon="chatbubbles-outline" title="All quiet on the support front" description="Passenger and driver requests will appear here." />}
    </ScrollView>
    <Sheet visible={!!ticket} onClose={() => setTicket(null)} title="Reply to support request">
      <Notice message={message} />
      <Field label="Your reply" testID="support-reply-input" value={reply} onChangeText={setReply} multiline />
      <Select label="Ticket status" testID="support-status-input" value={status} options={['OPEN', 'IN_PROGRESS', 'RESOLVED'].map(v => ({ label: v, value: v }))} onChange={setStatus} />
      <Button title="Send reply" testID="send-support-reply-button" onPress={save} loading={busy} />
    </Sheet>
  </>;
}