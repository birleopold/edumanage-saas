import React, { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { getJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function MessagesScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { getJson(mobilePaths.messages).then(setData).finally(() => setLoading(false)); }, []);

  return <ScreenShell title="Messages" loading={loading} error="">
    {(data?.announcements || []).map((a: any) => <Card key={`a-${a.id}`}><Label>Notice</Label><Value>{a.title}</Value><Text>{a.body}</Text></Card>)}
    {(data?.conversations || []).map((c: any) => <Card key={`c-${c.id}`}><Label>Conversation</Label><Value>{c.subject || 'Conversation'}</Value><Text>Unread: {c.unread_count}</Text></Card>)}
  </ScreenShell>;
}
