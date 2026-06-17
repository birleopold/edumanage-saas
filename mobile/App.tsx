import React, { useState } from 'react';
import { SafeAreaView, ScrollView, Text, TouchableOpacity, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { DashboardScreen } from './src/screens/DashboardScreen';
import { FinanceScreen } from './src/screens/FinanceScreen';
import { AttendanceScreen } from './src/screens/AttendanceScreen';
import { ExamsScreen } from './src/screens/ExamsScreen';
import { CourseworkScreen } from './src/screens/CourseworkScreen';
import { MessagesScreen } from './src/screens/MessagesScreen';
import { RoutesScreen } from './src/screens/RoutesScreen';
import { PushScreen } from './src/screens/PushScreen';

const tabs = ['Dashboard', 'Finance', 'Attendance', 'Exams', 'Coursework', 'Messages', 'Routes', 'Alerts'];

export default function App() {
  const [tab, setTab] = useState('Dashboard');

  function body() {
    if (tab === 'Finance') return <FinanceScreen />;
    if (tab === 'Attendance') return <AttendanceScreen />;
    if (tab === 'Exams') return <ExamsScreen />;
    if (tab === 'Coursework') return <CourseworkScreen />;
    if (tab === 'Messages') return <MessagesScreen />;
    if (tab === 'Routes') return <RoutesScreen />;
    if (tab === 'Alerts') return <PushScreen />;
    return <DashboardScreen />;
  }

  return <SafeAreaView style={{ flex: 1, backgroundColor: '#f8fafc' }}><StatusBar style="dark" /><View style={{ padding: 16, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' }}><Text style={{ fontSize: 24, fontWeight: '900', color: '#111827' }}>EduManage Mobile</Text></View><ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ maxHeight: 58, backgroundColor: '#fff' }} contentContainerStyle={{ paddingHorizontal: 12, paddingVertical: 10 }}>{tabs.map((item) => <TouchableOpacity key={item} onPress={() => setTab(item)} style={{ paddingHorizontal: 14, paddingVertical: 9, borderRadius: 999, backgroundColor: tab === item ? '#2563eb' : '#f1f5f9', marginRight: 8 }}><Text style={{ color: tab === item ? '#fff' : '#334155', fontWeight: '800' }}>{item}</Text></TouchableOpacity>)}</ScrollView>{body()}</SafeAreaView>;
}
