import React, { useEffect, useState } from 'react';
import { SafeAreaView, ScrollView, Text, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'https://your-school-domain.com/api/v1';

export default function App() {
  const [apiStatus, setApiStatus] = useState('Checking tenant API...');

  useEffect(() => {
    fetch(`${API_BASE_URL}/whoami/`)
      .then((response) => response.json())
      .then((data) => setApiStatus(`Connected to tenant: ${data.tenant || 'public'}`))
      .catch(() => setApiStatus('API not reachable yet. Check EXPO_PUBLIC_API_BASE_URL.'));
  }, []);

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#f8fafc' }}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <Text style={{ fontSize: 30, fontWeight: '800', color: '#111827', marginBottom: 8 }}>EduManage Mobile</Text>
        <Text style={{ fontSize: 16, color: '#4b5563', marginBottom: 24 }}>{apiStatus}</Text>
        <View style={{ backgroundColor: '#ffffff', borderRadius: 16, padding: 18, marginBottom: 16 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', marginBottom: 8 }}>Parent App</Text>
          <Text style={{ color: '#4b5563' }}>Dashboard, children, invoices, payments, results, coursework, transport, and announcements.</Text>
        </View>
        <View style={{ backgroundColor: '#ffffff', borderRadius: 16, padding: 18, marginBottom: 16 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', marginBottom: 8 }}>Student App</Text>
          <Text style={{ color: '#4b5563' }}>Coursework, online exams, attendance, finance status, messages, and transport details.</Text>
        </View>
        <View style={{ backgroundColor: '#ffffff', borderRadius: 16, padding: 18 }}>
          <Text style={{ fontSize: 18, fontWeight: '700', marginBottom: 8 }}>Teacher App</Text>
          <Text style={{ color: '#4b5563' }}>Mobile attendance marking, assigned classes, exam attempts, coursework, and messages.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
