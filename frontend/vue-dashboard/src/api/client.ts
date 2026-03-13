export interface DeviceRecord {
  mac_address: string;
  device_name: string;
  status: string;
}

export interface HealthSample {
  device_mac: string;
  timestamp: string;
  heart_rate: number;
  temperature: number;
  blood_oxygen: number;
  blood_pressure: string;
  battery: number;
  sos_flag: boolean;
  health_score?: number | null;
}

export interface AlarmRecord {
  id: string;
  device_mac: string;
  alarm_type: string;
  alarm_level: number;
  message: string;
  acknowledged: boolean;
  created_at: string;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
const WS_BASE = (import.meta.env.VITE_WS_BASE ?? "ws://localhost:8000").replace(/\/$/, "");

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  listDevices: () => requestJson<DeviceRecord[]>(`${API_BASE}/devices`),
  getRealtime: (mac: string) => requestJson<HealthSample>(`${API_BASE}/health/realtime/${mac}`),
  getTrend: (mac: string) => requestJson<HealthSample[]>(`${API_BASE}/health/trend/${mac}?minutes=180&limit=120`),
  listAlarms: () => requestJson<AlarmRecord[]>(`${API_BASE}/alarms?active_only=true`),
  ackAlarm: (alarmId: string) => requestJson<AlarmRecord>(`${API_BASE}/alarms/${alarmId}/acknowledge`, { method: "POST" }),
  analyze: (payload: { device_mac: string; question: string; role: string; mode: string }) =>
    requestJson<{ answer: string; references: string[] }>(`${API_BASE}/chat/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  healthSocket: (mac: string) => new WebSocket(`${WS_BASE}/ws/health/${mac}`),
  alarmSocket: () => new WebSocket(`${WS_BASE}/ws/alarms`),
};
