import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { api } from '../services/api';
import type { AppSettings } from '../types';

interface DataContextValue {
  lastUpdated: string | null;
  dataSource: string;
  warnings: string[];
  refreshing: boolean;
  settings: AppSettings | null;
  unreadCount: number;
  refresh: (retrain?: boolean) => Promise<void>;
  reloadSettings: () => Promise<void>;
  tick: number;
}

const DataContext = createContext<DataContextValue | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [dataSource, setDataSource] = useState('—');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [tick, setTick] = useState(0);
  const intervalRef = useRef<number | null>(null);

  const reloadSettings = useCallback(async () => {
    const s = await api.settings();
    setSettings(s);
  }, []);

  const refresh = useCallback(async (retrain = false) => {
    setRefreshing(true);
    try {
      await api.refresh(retrain);
      const [health, notes] = await Promise.all([
        api.health() as Promise<{
          last_updated?: string;
          data_source?: string;
          warnings?: string[];
        }>,
        api.notifications({ unread_only: 'true' }),
      ]);
      setLastUpdated(health.last_updated || new Date().toISOString());
      setDataSource(health.data_source || '—');
      setWarnings(health.warnings || []);
      setUnreadCount(notes.length);
      setTick((t) => t + 1);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    reloadSettings()
      .then(() => refresh(false))
      .catch(console.error);
  }, [refresh, reloadSettings]);

  useEffect(() => {
    if (intervalRef.current) window.clearInterval(intervalRef.current);
    const ms = (settings?.refresh_interval_seconds || 30) * 1000;
    intervalRef.current = window.setInterval(() => {
      refresh(false).catch(console.error);
    }, ms);
    return () => {
      if (intervalRef.current) window.clearInterval(intervalRef.current);
    };
  }, [settings?.refresh_interval_seconds, refresh]);

  return (
    <DataContext.Provider
      value={{
        lastUpdated,
        dataSource,
        warnings,
        refreshing,
        settings,
        unreadCount,
        refresh,
        reloadSettings,
        tick,
      }}
    >
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
