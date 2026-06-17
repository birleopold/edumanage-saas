import React, { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { getJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function CourseworkScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { getJson(mobilePaths.coursework).then(setData).finally(() => setLoading(false)); }, []);

  return <ScreenShell title="Coursework" loading={loading} error="">
    {(data?.students || []).map((item: any) => item.assignments.map((a: any) => <Card key={`${item.student.id}-a-${a.id}`}><Label>{item.student.name}</Label><Value>{a.title}</Value><Text>{a.submitted ? 'Submitted' : 'Pending'}</Text><Text>{a.due_date || ''}</Text></Card>))}
    {(data?.materials || []).map((m: any) => <Card key={`m-${m.id}`}><Label>Material</Label><Value>{m.title}</Value><Text>{m.course}</Text></Card>)}
  </ScreenShell>;
}
