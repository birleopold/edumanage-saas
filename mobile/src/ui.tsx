import React from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';

export function ScreenShell({ title, loading, error, children }: any) {
  return <ScrollView contentContainerStyle={{ padding: 16 }}><Text style={{ fontSize: 24, fontWeight: '900', color: '#111827', marginBottom: 12 }}>{title}</Text>{loading ? <ActivityIndicator /> : null}{error ? <Text style={{ color: '#dc2626', marginBottom: 12 }}>{error}</Text> : null}{children}</ScrollView>;
}

export function Card({ children }: any) {
  return <View style={{ backgroundColor: '#ffffff', borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#e5e7eb' }}>{children}</View>;
}

export function Label({ children }: any) {
  return <Text style={{ fontSize: 12, fontWeight: '800', color: '#64748b' }}>{children}</Text>;
}

export function Value({ children }: any) {
  return <Text style={{ fontSize: 18, fontWeight: '900', color: '#111827', marginTop: 4 }}>{children}</Text>;
}
