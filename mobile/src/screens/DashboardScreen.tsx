import React, { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { getJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function DashboardScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getJson(mobilePaths.dashboard).then(setData).catch(() => setError('Could not load dashboard.')).finally(() => setLoading(false));
  }, []);

  const counts = data?.counts || {};

  return <ScreenShell title="Dashboard" loading={loading} error={error}>
    <Card><Label>User</Label><Value>{data?.profile?.username || 'Account'}</Value><Text>{(data?.profile?.roles || []).join(', ')}</Text></Card>
    <Card><Label>Invoices</Label><Value>{counts.invoices || 0}</Value></Card>
    <Card><Label>Open Balance</Label><Value>{String(counts.open_balance || 0)}</Value></Card>
    <Card><Label>Coursework Items</Label><Value>{counts.coursework_items || 0}</Value></Card>
    <Card><Label>Published Results</Label><Value>{counts.published_results || 0}</Value></Card>
  </ScreenShell>;
}
