import React, { useState } from 'react';
import { ScrollView, Text, TextInput, TouchableOpacity } from 'react-native';
import { signIn } from '../apiClient';
import { API_BASE_URL } from '../config';

export function LoginScreen({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  async function submit() {
    setError('');
    try {
      await signIn(username, password);
      onDone();
    } catch (e) {
      setError('Login failed. Check your account and school URL.');
    }
  }

  return <ScrollView contentContainerStyle={{ padding: 24 }}><Text style={{ fontSize: 32, fontWeight: '900', color: '#111827', marginTop: 48 }}>EduManage Mobile</Text><Text style={{ color: '#64748b', marginTop: 8, marginBottom: 24 }}>{API_BASE_URL}</Text><TextInput value={username} onChangeText={setUsername} autoCapitalize="none" placeholder="Username" style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: '#d1d5db', borderRadius: 12, padding: 14, marginBottom: 12 }} /><TextInput value={password} onChangeText={setPassword} placeholder="Password" secureTextEntry style={{ backgroundColor: '#fff', borderWidth: 1, borderColor: '#d1d5db', borderRadius: 12, padding: 14, marginBottom: 12 }} />{error ? <Text style={{ color: '#dc2626', marginBottom: 12 }}>{error}</Text> : null}<TouchableOpacity onPress={submit} style={{ backgroundColor: '#2563eb', padding: 15, borderRadius: 12, alignItems: 'center' }}><Text style={{ color: '#fff', fontWeight: '900' }}>Login</Text></TouchableOpacity></ScrollView>;
}
