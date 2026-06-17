import React, { useState } from 'react';
import { Text, TouchableOpacity } from 'react-native';
import * as Notifications from 'expo-notifications';
import { postJson } from '../apiClient';
import { mobilePaths } from '../config';
import { Card, ScreenShell, Value } from '../ui';

export function PushScreen() {
  const [message, setMessage] = useState('Not registered yet.');

  async function register() {
    const permission = await Notifications.requestPermissionsAsync();
    if (!permission.granted) { setMessage('Permission not granted.'); return; }
    const token = await Notifications.getExpoPushTokenAsync();
    await postJson(mobilePaths.registerDevice, { platform: 'ANDROID', device_id: token.data.slice(-24), push_token: token.data, app_version: '0.2.0' });
    setMessage('Device registered.');
  }

  return <ScreenShell title="Notifications" loading={false} error="">
    <Card><Value>{message}</Value><Text>Register this device for school notices and alerts.</Text><TouchableOpacity onPress={register} style={{ backgroundColor: '#2563eb', padding: 12, borderRadius: 10, marginTop: 12 }}><Text style={{ color: '#fff', fontWeight: '800', textAlign: 'center' }}>Register Device</Text></TouchableOpacity></Card>
  </ScreenShell>;
}
