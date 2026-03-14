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
  blood_pressure?: string;
  battery?: number;
  sos_flag?: boolean;
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

export interface AgentResponse {
  scope: string;
  mode: string;
  network_online: boolean;
  answer: string;
  references: string[];
  analysis?: Record<string, unknown>;
}

export interface CommunityOverview {
  clusters: Record<string, string[]>;
  device_count: number;
  intelligent_anomaly_score: number;
}

export interface CommunityProfile {
  id: string;
  name: string;
  address: string;
  manager: string;
  hotline: string;
}

export interface ElderProfile {
  id: string;
  name: string;
  age: number;
  apartment: string;
  community_id: string;
  device_mac: string;
  family_ids: string[];
}

export interface FamilyProfile {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  community_id: string;
  elder_ids: string[];
  login_username: string;
}

export interface CareDirectory {
  community: CommunityProfile;
  elders: ElderProfile[];
  families: FamilyProfile[];
}

export interface SessionUser {
  id: string;
  username: string;
  name: string;
  role: "family" | "community" | "admin" | "elder";
  community_id: string;
  family_id?: string | null;
}

export interface AuthAccountPreview {
  username: string;
  display_name: string;
  role: "family" | "community" | "admin" | "elder";
  family_id?: string | null;
  community_id: string;
  default_password: string;
}

export interface LoginResponse {
  token: string;
  user: SessionUser;
  expires_at: string;
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

function withBearer(token?: string): HeadersInit | undefined {
  if (!token) return undefined;
  return { Authorization: `Bearer ${token}` };
}

export const api = {
  listDevices: () => requestJson<DeviceRecord[]>(`${API_BASE}/devices`),
  getRealtime: (mac: string) => requestJson<HealthSample>(`${API_BASE}/health/realtime/${mac}`),
  getTrend: (mac: string, minutes = 180, limit = 120) =>
    requestJson<HealthSample[]>(`${API_BASE}/health/trend/${mac}?minutes=${minutes}&limit=${limit}`),
  getCommunityOverview: () =>
    requestJson<CommunityOverview>(`${API_BASE}/health/community/overview`),
  listAlarms: () => requestJson<AlarmRecord[]>(`${API_BASE}/alarms?active_only=true`),
  ackAlarm: (alarmId: string) =>
    requestJson<AlarmRecord>(`${API_BASE}/alarms/${alarmId}/acknowledge`, { method: "POST" }),
  analyze: (payload: {
    device_mac: string;
    question: string;
    role: string;
    mode: string;
    history_limit?: number;
    history_minutes?: number;
  }) =>
    requestJson<AgentResponse>(`${API_BASE}/chat/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  analyzeCommunity: (payload: {
    question: string;
    role: string;
    mode: string;
    history_minutes?: number;
    per_device_limit?: number;
    device_macs?: string[];
  }) =>
    requestJson<AgentResponse>(`${API_BASE}/chat/analyze/community`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getCareDirectory: () => requestJson<CareDirectory>(`${API_BASE}/care/directory`),
  getFamilyCareDirectory: (familyId: string) =>
    requestJson<CareDirectory>(`${API_BASE}/care/directory/family/${familyId}`),
  listMockAccounts: () =>
    requestJson<AuthAccountPreview[]>(`${API_BASE}/auth/mock-accounts`),
  loginMock: (payload: { username: string; password: string }) =>
    requestJson<LoginResponse>(`${API_BASE}/auth/mock-login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  me: (token: string) =>
    requestJson<SessionUser>(`${API_BASE}/auth/me`, {
      headers: withBearer(token),
    }),
  healthSocket: (mac: string) => new WebSocket(`${WS_BASE}/ws/health/${mac}`),
  alarmSocket: () => new WebSocket(`${WS_BASE}/ws/alarms`),
};
