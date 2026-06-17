import React, { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { getJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function AttendanceScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { getJson(mobilePaths.attendance).then(setData).finally(() => setLoading(false)); }, []);

  return <ScreenShell title="Attendance" loading={loading} error="">
    {(data?.entries || []).map((entry: any) => <Card key={entry.id}><Label>{entry.date}</Label><Value>{entry.status}</Value><Text>{entry.course}</Text></Card>)}
    {(data?.offerings || []).map((offering: any) => <Card key={offering.id}><Label>Class</Label><Value>{offering.course}</Value><Text>{offering.term}</Text></Card>)}
  </ScreenShell>;
}
