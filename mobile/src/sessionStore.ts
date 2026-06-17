import { deleteItemAsync, getItemAsync, setItemAsync } from 'expo-secure-store';

const SESSION_KEY = 'edumanage_session';

export const sessionStore = {
  save: (value: string) => setItemAsync(SESSION_KEY, value),
  load: () => getItemAsync(SESSION_KEY),
  clear: () => deleteItemAsync(SESSION_KEY),
};
