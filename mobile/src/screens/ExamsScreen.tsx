import React, { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { getJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function ExamsScreen() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { getJson(mobilePaths.exams).then(setData).finally(() => setLoading(false)); }, []);

  return <ScreenShell title="Exams" loading={loading} error="">
    {(data?.students || []).map((item: any) => item.papers.map((paper: any) => <Card key={`${item.student.id}-${paper.id}`}><Label>{item.student.name}</Label><Value>{paper.course}</Value><Text>{paper.exam}</Text><Text>{paper.attempt_status || 'Not attempted'}</Text><Text>{paper.grade ? `Grade: ${paper.grade}` : ''}</Text></Card>))}
  </ScreenShell>;
}
