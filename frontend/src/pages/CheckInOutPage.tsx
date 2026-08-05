import { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../services/api';
import { useData } from '../hooks/useData';

/**
 * Architecture workflow:
 *   Check-Out (Dispatch) = start rental → POST /api/check-in (CSV Check-In semantics)
 *   Check-In (Return)    = end rental   → POST /api/check-out
 */
export function CheckInOutPage() {
  const { refresh } = useData();
  const [tab, setTab] = useState<'dispatch' | 'return'>('dispatch');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [dispatch, setDispatch] = useState({
    equipment_id: '',
    site_id: '',
    operator_id: '',
    check_in_date: new Date().toISOString().slice(0, 10),
    expected_return_date: '',
  });

  const [ret, setRet] = useState({
    equipment_id: '',
    actual_return_date: new Date().toISOString().slice(0, 10),
    final_engine_hours: '',
    condition_notes: '',
  });

  async function submitDispatch(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await api.checkIn(dispatch);
      setMessage(
        'Dispatch complete — Contract Lambda created ACTIVE RentalContract (Check-Out / Dispatch).',
      );
      await refresh(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitReturn(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body: Record<string, unknown> = {
        equipment_id: ret.equipment_id,
        actual_return_date: ret.actual_return_date,
        condition_notes: ret.condition_notes || null,
      };
      if (ret.final_engine_hours !== '') {
        body.final_engine_hours = Number(ret.final_engine_hours);
      }
      await api.checkOut(body);
      setMessage('Return complete — contract marked RETURNED (Check-In / Return).');
      await refresh(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const qrValue = tab === 'dispatch' ? dispatch.equipment_id : ret.equipment_id;

  return (
    <div className="page max-w-3xl">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cat-gray">
          Mobile App / Scanner → API Gateway → Contract Lambda
        </p>
        <h2 className="page-title">Dispatch / Return</h2>
        <p className="page-sub">
          Architecture: <strong>Check-Out = Dispatch</strong> · <strong>Check-In = Return</strong>.
          QR/RFID ready.
        </p>
      </div>

      <div className="flex gap-6 border-b border-cat-muted">
        <button
          type="button"
          onClick={() => setTab('dispatch')}
          className={`pb-2 text-sm font-semibold ${tab === 'dispatch' ? 'border-b-2 border-cat-yellow text-cat-black' : 'text-cat-gray'}`}
        >
          Check-Out (Dispatch)
        </button>
        <button
          type="button"
          onClick={() => setTab('return')}
          className={`pb-2 text-sm font-semibold ${tab === 'return' ? 'border-b-2 border-cat-yellow text-cat-black' : 'text-cat-gray'}`}
        >
          Check-In (Return)
        </button>
      </div>

      {message && <p className="text-sm font-medium text-emerald-700">{message}</p>}
      {error && <p className="text-sm font-medium text-red-700">{error}</p>}

      <div className="grid gap-10 md:grid-cols-[1fr_160px]">
        {tab === 'dispatch' ? (
          <form className="space-y-5" onSubmit={submitDispatch}>
            <Field label="Equipment ID">
              <input
                required
                className="field w-full"
                value={dispatch.equipment_id}
                onChange={(e) => setDispatch({ ...dispatch, equipment_id: e.target.value.toUpperCase() })}
                placeholder="EQX1001"
              />
            </Field>
            <Field label="Site ID">
              <input
                required
                className="field w-full"
                value={dispatch.site_id}
                onChange={(e) => setDispatch({ ...dispatch, site_id: e.target.value.toUpperCase() })}
                placeholder="S003"
              />
            </Field>
            <Field label="Operator ID (RFID)">
              <input
                required
                className="field w-full"
                value={dispatch.operator_id}
                onChange={(e) => setDispatch({ ...dispatch, operator_id: e.target.value.toUpperCase() })}
                placeholder="OP101"
              />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Dispatch Date">
                <input
                  required
                  type="date"
                  className="field w-full"
                  value={dispatch.check_in_date}
                  onChange={(e) => setDispatch({ ...dispatch, check_in_date: e.target.value })}
                />
              </Field>
              <Field label="Expected Return Date">
                <input
                  required
                  type="date"
                  className="field w-full"
                  value={dispatch.expected_return_date}
                  onChange={(e) => setDispatch({ ...dispatch, expected_return_date: e.target.value })}
                />
              </Field>
            </div>
            <button type="submit" disabled={busy} className="btn-accent">
              {busy ? 'Invoking Contract Lambda…' : 'Confirm Dispatch'}
            </button>
          </form>
        ) : (
          <form className="space-y-5" onSubmit={submitReturn}>
            <Field label="Equipment ID">
              <input
                required
                className="field w-full"
                value={ret.equipment_id}
                onChange={(e) => setRet({ ...ret, equipment_id: e.target.value.toUpperCase() })}
                placeholder="EQX1008"
              />
            </Field>
            <Field label="Actual Return Date">
              <input
                required
                type="date"
                className="field w-full"
                value={ret.actual_return_date}
                onChange={(e) => setRet({ ...ret, actual_return_date: e.target.value })}
              />
            </Field>
            <Field label="Final Engine Hours (optional)">
              <input
                type="number"
                step="0.1"
                min="0"
                className="field w-full"
                value={ret.final_engine_hours}
                onChange={(e) => setRet({ ...ret, final_engine_hours: e.target.value })}
              />
            </Field>
            <Field label="Condition / Notes">
              <textarea
                className="field w-full resize-none"
                rows={3}
                value={ret.condition_notes}
                onChange={(e) => setRet({ ...ret, condition_notes: e.target.value })}
              />
            </Field>
            <button type="submit" disabled={busy} className="btn-accent">
              {busy ? 'Invoking Contract Lambda…' : 'Confirm Return'}
            </button>
          </form>
        )}

        <div className="flex flex-col items-center gap-2 pt-2">
          {qrValue ? (
            <QRCodeSVG value={qrValue} size={132} />
          ) : (
            <div className="flex h-32 w-32 items-center justify-center border border-dashed border-cat-muted text-[10px] text-cat-gray">
              Scan / Enter ID
            </div>
          )}
          <p className="text-center text-[11px] text-cat-gray">QR / RFID</p>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
      {label}
      {children}
    </label>
  );
}
