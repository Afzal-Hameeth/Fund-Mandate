import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { API } from '../utils/constants';
import toast from 'react-hot-toast';

const toDisplayArray = (obj: any) => {
  if (!obj) return [];
  if (Array.isArray(obj)) {
    return obj.map((item: any) => {
      if (typeof item === 'string') return { key: item, value: '' };
      if (typeof item === 'object') {
        const entries = Object.entries(item)[0] ?? [];
        return { key: String(entries[0] ?? ''), value: String(entries[1] ?? '') };
      }
      return { key: String(item), value: '' };
    });
  }
  if (typeof obj === 'object') {
    return Object.entries(obj).map(([k, v]) => ({ key: k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), value: String(v) }));
  }
  return [{ key: String(obj), value: '' }];
};

const SourcingAgent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const state = (location.state as any) ?? {};
  const parsed = state.parsedResult ?? null;

  // Prefer explicit `sourcing` passed via navigation state, else attempt to derive from parsed result
  const sourcingFromState = state.sourcing ?? null;
  const derivedFromParsed = parsed?.criteria?.mandate?.sourcing_parameters ?? parsed?.criteria?.fund_mandate?.sourcing_parameters ?? null;

  const sourcingList = sourcingFromState ?? toDisplayArray(derivedFromParsed);
  const [selectedKeys, setSelectedKeys] = useState<Record<string, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const toggleSelect = (key: string) => {
    setSelectedKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const getSelectedItems = () => sourcingList.filter((s: any) => selectedKeys[s.key]);

  const handleContinue = async () => {
    const items = getSelectedItems();
    if (!items || items.length === 0) {
      toast.error('Please select at least one threshold to continue');
      return;
    }

    setIsSubmitting(true);
    try {
      const resp = await fetch(`${API.BASE_URL()}${API.ENDPOINTS.FILTER.COMPANIES()}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_thresholds: items }),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || `Server error ${resp.status}`);
      }

      const data = await resp.json();
      console.log('Filter companies response:', data);
      toast.success('Sent selected thresholds to backend');
    } catch (err) {
      console.error('Error sending selected thresholds:', err);
      toast.error('Failed to send to backend');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col min-h-full bg-gray-50">
      <header className="border-b sticky top-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div>
                <h1 className="text-xl font-bold">Sourcing Agent</h1>
                <p className="text-xs text-muted-foreground">Select thresholds to filter and source companies</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="p-8">
      {sourcingList && sourcingList.length > 0 ? (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-gray-800">Mandatory Thresholds (Sourcing)</h2>
          <div className="flex gap-4 overflow-x-auto py-2">
            {sourcingList.map((threshold: any) => {
              const selected = !!selectedKeys[threshold.key];
              return (
                <label
                  key={threshold.key}
                  className={`min-w-[260px] flex-shrink-0 flex items-start gap-3 p-3 rounded-lg border transition-colors text-left cursor-pointer ${selected ? 'bg-indigo-50 border-indigo-300 ring-2 ring-indigo-200' : 'bg-gray-50 border-gray-200 hover:border-indigo-200'}`}
                >
                  <input
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleSelect(threshold.key)}
                    className="w-3 h-3 mt-1 text-indigo-600 rounded"
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-gray-800">{threshold.key}</span>
                    </div>
                    <div className="text-sm text-gray-600 mt-2">{threshold.value}</div>
                  </div>
                </label>
              );
            })}
          </div>
          <div className="flex justify-end pt-4">
            <button
              onClick={handleContinue}
              disabled={isSubmitting || getSelectedItems().length === 0}
              className={`px-4 py-2 rounded-lg font-medium ${(isSubmitting || getSelectedItems().length === 0) ? 'bg-gray-300 text-gray-600 cursor-not-allowed' : 'bg-indigo-600 text-white hover:bg-indigo-700'}`}
            >
              {isSubmitting ? 'Sending...' : 'Continue'}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-600">No sourcing thresholds found. Navigate from Fund Mandate after upload.</p>
      )} 

      
    </div>
    </div>
  );
};

export default SourcingAgent;
