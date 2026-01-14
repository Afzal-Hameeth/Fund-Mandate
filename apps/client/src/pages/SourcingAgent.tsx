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

const formatValue = (key: string, value: any): string => {
  if (value === null || value === undefined) return '-';

  const currencyKeys = ['Revenue', 'Net Income', 'Total Assets', 'Total Equity', 'EBITDA', 'Market Cap'];
  const percentageKeys = ['Dividend Yield', 'Return on Equity', 'Gross Profit Margin', '1-Year Change'];

  if (currencyKeys.includes(key) && typeof value === 'string') {
    // Handle strings like "11.14B", "244.12B."
    const cleaned = value.replace(/[$,.]/g, '');
    if (cleaned.includes('B')) {
      return value; // Already formatted
    }
    if (cleaned.includes('M')) {
      return value;
    }
    // If it's a number string, format it
    const num = parseFloat(cleaned);
    if (!isNaN(num)) {
      if (Math.abs(num) >= 1000000000) {
        return `$${(num / 1000000000).toFixed(2)}B`;
      } else if (Math.abs(num) >= 1000000) {
        return `$${(num / 1000000).toFixed(2)}M`;
      } else if (Math.abs(num) >= 1000) {
        return `$${(num / 1000).toFixed(2)}K`;
      }
      return `$${num.toFixed(2)}`;
    }
  }

  if (percentageKeys.includes(key) && typeof value === 'string') {
    const cleaned = value.replace(/[%]/g, '');
    const num = parseFloat(cleaned);
    if (!isNaN(num)) {
      return `${num.toFixed(2)}%`;
    }
  }

  if (key === 'Debt / Equity' && typeof value === 'number') {
    return value.toFixed(4);
  }

  if (key === 'P/E Ratio' && typeof value === 'number') {
    return value.toFixed(2);
  }

  if (key === 'Price/Book' && typeof value === 'number') {
    return value.toFixed(2);
  }

  return String(value).trim();
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
  const [filterResponse, setFilterResponse] = useState<any>(null);

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
    setFilterResponse(null);

    try {
      // Construct payload in the required format: {"additionalProp1": {selected_parameters}}
      const selectedParams: Record<string, string> = {};
      items.forEach((item: any) => {
        selectedParams[item.key.toLowerCase().replace(/\s+/g, '_')] = item.value;
      });

      const payload = {
        additionalProp1: selectedParams
      };

      console.log('Sending payload:', payload);

      const resp = await fetch(`${API.BASE_URL()}${API.ENDPOINTS.FILTER.COMPANIES()}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || `Server error ${resp.status}`);
      }

      const data = await resp.json();
      console.log('Filter companies response:', data);
      
      // Store the response to display it
      setFilterResponse(data);
      
      toast.success('Successfully filtered companies based on selected parameters');
    } catch (err) {
      console.error('Error sending selected thresholds:', err);
      toast.error('Failed to filter companies');
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

      {/* Display Filter Response */}
      {filterResponse && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Filtered Companies Result</h2>
          {(() => {
            const qualified = filterResponse.companies?.qualified || [];
            const columns = qualified.length > 0 ? Object.keys(qualified[0]) : [];
            return qualified.length > 0 ? (
              <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                <div className="overflow-x-auto overflow-y-auto max-h-[500px]">
                  <table className="w-full">
                    <thead className="sticky top-0 z-10">
                      <tr className="bg-[#BEBEBE]">
                        <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">S.No.</th>
                        {columns.map((col) => (
                          <th
                            key={col}
                            className={`px-3 py-3 text-xs font-bold text-black whitespace-nowrap ${
                              col === 'Company ' ? 'text-left' : 'text-center'
                            }`}
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {qualified.map((row: any, index: number) => (
                        <tr key={index} className="hover:bg-blue-50 transition-colors cursor-pointer">
                          <td className="px-3 py-3 text-sm text-black">{index + 1}.</td>
                          {columns.map((col) => (
                            <td
                              key={col}
                              className={`px-3 py-3 text-sm whitespace-nowrap ${
                                col === 'Company '
                                  ? 'text-left text-indigo-600 font-bold'
                                  : 'text-center text-black'
                              }`}
                            >
                              {formatValue(col, row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-600">No qualified companies found in the response.</p>
              </div>
            );
          })()}
        </div>
      )}
      
    </div>
    </div>
  );
};

export default SourcingAgent;
