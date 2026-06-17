import { API_BASE_URL } from './config';

let accessValue = '';

export function setAccess(value: string) {
  accessValue = value;
}

export async function signIn(username: string, password: string) {
  const response = await fetch(`${API_BASE_URL}/auth/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) throw new Error('Login failed');
  const data = await response.json();
  setAccess(data.access);
  return data;
}

export async function getJson(path: string) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: accessValue ? { Authorization: `Bearer ${accessValue}` } : {},
  });
  if (!response.ok) throw new Error(`Request failed ${response.status}`);
  return response.json();
}

export async function postJson(path: string, body: unknown) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(accessValue ? { Authorization: `Bearer ${accessValue}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Request failed ${response.status}`);
  return response.json();
}
