import React, { useEffect, useState } from 'react';
import { Text, TextInput, TouchableOpacity, View } from 'react-native';
import { getJson, postJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, Label, ScreenShell, Value } from '../ui';

export function FinanceScreen() {
  const [data, setData] = useState<any>(null);
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState('');

  function load() {
    setLoading(true);
    getJson(mobilePaths.finance).then(setData).finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function requestPayment(invoiceId: number, amount: any) {
    if (!phone) { setMessage('Enter phone number first.'); return; }
    await postJson(`/mobile/finance/invoices/${invoiceId}/pay/`, { amount, phone_number: phone, network: 'MTN_MOMO' });
    setMessage('Payment request created.');
    load();
  }

  return <ScreenShell title="Finance" loading={loading} error="">
    <Card><Label>Payment Phone</Label><TextInput value={phone} onChangeText={setPhone} placeholder="2567XXXXXXXX" style={{ borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, padding: 10, marginTop: 8 }} />{message ? <Text style={{ marginTop: 8 }}>{message}</Text> : null}</Card>
    {(data?.invoices || []).map((inv: any) => <Card key={inv.id}><Label>{inv.reference || `Invoice ${inv.id}`}</Label><Value>{String(inv.balance)}</Value><Text>{inv.display_status}</Text><TouchableOpacity onPress={() => requestPayment(inv.id, inv.balance)} style={{ backgroundColor: '#16a34a', padding: 12, borderRadius: 10, marginTop: 10 }}><Text style={{ color: '#fff', fontWeight: '800', textAlign: 'center' }}>Request Mobile Payment</Text></TouchableOpacity></Card>)}
    <View style={{ height: 20 }} />
  </ScreenShell>;
}
