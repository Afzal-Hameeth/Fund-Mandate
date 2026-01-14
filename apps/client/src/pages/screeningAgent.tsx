import React, { useState } from 'react';
import { FiPlay } from 'react-icons/fi';

const ScreeningAgent: React.FC = () => {
  const [companies, setCompanies] = useState<Record<string, any>[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchScreeningData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/screening/companies');
      if (!response.ok) {
        throw new Error('Failed to fetch screening data');
      }
      const data = await response.json();
      const qualified = data.qualified || [];
      setCompanies(qualified);
      if (qualified.length > 0) {
        setColumns(Object.keys(qualified[0]));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const formatValue = (key: string, value: any): string => {
    if (value === null || value === undefined) return '-';

    const currencyKeys = ['Revenue', 'Net Income', 'Total Assets', 'Total Equity'];
    const percentageKeys = ['Dividend Yield', 'Return on Equity'];

    if (currencyKeys.includes(key) && typeof value === 'number') {
      if (Math.abs(value) >= 1000000000) {
        return `$${(value / 1000000000).toFixed(2)}B`;
      } else if (Math.abs(value) >= 1000000) {
        return `$${(value / 1000000).toFixed(2)}M`;
      } else if (Math.abs(value) >= 1000) {
        return `$${(value / 1000).toFixed(2)}K`;
      }
      return `$${value.toFixed(2)}`;
    }

    if (percentageKeys.includes(key) && typeof value === 'number') {
      return `${(value * 100).toFixed(2)}%`;
    }

    if (key === 'Debt / Equity' && typeof value === 'number') {
      return value.toFixed(4);
    }

    return String(value).trim();
  };

  return (
    <div className="flex flex-col h-full p-8 bg-white">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Screening Agent</h1>
          <p className="text-gray-500 mt-1 text-sm">Investment screening parameters for risk assessment</p>
        </div>
        <button
          onClick={fetchScreeningData}
          disabled={isLoading}
          className={`px-4 py-2 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 ${
            isLoading
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-lg'
          }`}
        >
          {isLoading ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Loading...
            </>
          ) : (
            <>
              <FiPlay size={16} />
              Run Screening
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
          {error}
        </div>
      )}

      {companies.length === 0 && !isLoading && !error && (
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <p>Click "Run Screening" to fetch company data</p>
        </div>
      )}

      {companies.length > 0 && columns.length > 0 && (
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
                        col === 'Company' ? 'text-left' : 'text-center'
                      }`}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {companies.map((row, index) => (
                  <tr key={index} className="hover:bg-blue-50 transition-colors cursor-pointer">
                    <td className="px-3 py-3 text-sm text-black">{index + 1}.</td>
                    {columns.map((col) => (
                      <td
                        key={col}
                        className={`px-3 py-3 text-sm whitespace-nowrap ${
                          col === 'Company'
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
      )}
    </div>
  );
};

export default ScreeningAgent;
