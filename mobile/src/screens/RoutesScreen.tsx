import React, { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { getJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function RoutesScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { getJson(mobilePaths.transport).then(setData).finally(() => setLoading(false)); }, []);

  return <ScreenShell title="Routes" loading={loading} error="">
    {(data?.assignments || []).map((a: any) => <Card key={a.id}><Label>{a.student?.name}</Label><Value>{a.route}</Value><Text>{a.vehicle}</Text><Text>{a.stop}</Text></Card>)}
  </ScreenShell>;
}
