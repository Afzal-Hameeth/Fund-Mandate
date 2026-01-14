import React from 'react';

const mockData = [
  {
    company: 'TechVenture Inc.',
    country: 'United States',
    sector: 'Technology',
    industry: 'Software',
    revenue: '$2.4B',
    netIncome: '$320M',
    marketCap: '$18.5B',
    grossProfitMargin: '68.5%',
  },
  {
    company: 'Global Finance Corp',
    country: 'United Kingdom',
    sector: 'Financial Services',
    industry: 'Banking',
    revenue: '$8.1B',
    netIncome: '$1.2B',
    marketCap: '$42.3B',
    grossProfitMargin: '45.2%',
  },
  {
    company: 'HealthCare Solutions',
    country: 'Germany',
    sector: 'Healthcare',
    industry: 'Pharmaceuticals',
    revenue: '$5.6B',
    netIncome: '$780M',
    marketCap: '$28.9B',
    grossProfitMargin: '72.1%',
  },
  {
    company: 'RetailMax Holdings',
    country: 'Canada',
    sector: 'Consumer Discretionary',
    industry: 'Retail',
    revenue: '$12.3B',
    netIncome: '$450M',
    marketCap: '$15.7B',
    grossProfitMargin: '32.8%',
  },
  {
    company: 'EnergyPower Ltd',
    country: 'Australia',
    sector: 'Energy',
    industry: 'Oil & Gas',
    revenue: '$18.9B',
    netIncome: '$2.1B',
    marketCap: '$65.4B',
    grossProfitMargin: '41.5%',
  },
  {
    company: 'CloudNet Systems',
    country: 'United States',
    sector: 'Technology',
    industry: 'Cloud Computing',
    revenue: '$4.2B',
    netIncome: '$580M',
    marketCap: '$32.1B',
    grossProfitMargin: '71.3%',
  },
  {
    company: 'BioMed Research',
    country: 'Switzerland',
    sector: 'Healthcare',
    industry: 'Biotechnology',
    revenue: '$1.8B',
    netIncome: '$210M',
    marketCap: '$12.4B',
    grossProfitMargin: '78.9%',
  },
  {
    company: 'AutoDrive Motors',
    country: 'Japan',
    sector: 'Consumer Discretionary',
    industry: 'Automobiles',
    revenue: '$45.2B',
    netIncome: '$3.8B',
    marketCap: '$89.6B',
    grossProfitMargin: '22.4%',
  },
  {
    company: 'GreenEnergy Corp',
    country: 'Denmark',
    sector: 'Utilities',
    industry: 'Renewable Energy',
    revenue: '$6.7B',
    netIncome: '$890M',
    marketCap: '$38.2B',
    grossProfitMargin: '52.6%',
  },
  {
    company: 'DataStream Analytics',
    country: 'India',
    sector: 'Technology',
    industry: 'Data Services',
    revenue: '$980M',
    netIncome: '$145M',
    marketCap: '$7.8B',
    grossProfitMargin: '65.7%',
  },
];

const ScreeningAgent: React.FC = () => {
  return (
    <div className="flex flex-col h-full p-8 bg-white">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-800">Screening Agent</h1>
        <p className="text-gray-500 mt-1 text-sm">Investment screening parameters for risk assessment</p>
      </div>

      <div className="bg-white overflow-hidden max-h-[500px] rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
        <div className="overflow-x-auto overflow-y-auto max-h-[500px]">
          <table className="w-full">
            <thead className="sticky top-0 z-10">
              <tr className="bg-[#DBDBDB]">
                <th className="px-4 py-3 text-left text-xs font-bold text-black whitespace-nowrap">
                  S.No.
                </th>
                <th className="px-4 py-3 text-left text-xs font-bold text-black whitespace-nowrap">
                  Company
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Country
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Sector
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Industry
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Revenue
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Net Income
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Market Cap
                </th>
                <th className="px-4 py-3 text-center text-xs font-bold text-black whitespace-nowrap">
                  Gross Profit Margin
                </th>
              </tr>
            </thead>
            <tbody>
              {mockData.map((row, index) => (
                <tr key={index} className="hover:bg-blue-50 transition-colors cursor-pointer">
                  <td className="px-4 py-3 text-sm text-black">
                    {index + 1}.
                  </td>
                   <td className="px-4 py-3 text-sm text-indigo-600 font-bold whitespace-nowrap">
                    {row.company}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.country}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.sector}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.industry}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.revenue}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.netIncome}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.marketCap}
                  </td>
                  <td className="px-4 py-3 text-center text-sm text-black">
                    {row.grossProfitMargin}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ScreeningAgent;
