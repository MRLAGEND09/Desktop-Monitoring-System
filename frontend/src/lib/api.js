import axios from 'axios';
import { useAuthStore } from '../store/auth';

const API_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({ baseURL: API_URL, timeout: 15_000 });

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const token = useAuthStore.getState().token;
    const url = error.config?.url ?? '';
    if (error.response?.status === 401 && token && !url.includes('/auth/login')) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);

export default api;
