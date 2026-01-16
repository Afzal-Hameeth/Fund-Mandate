import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { API } from '../utils/constants';
import toast from 'react-hot-toast';
import { FiArrowLeft, FiArrowRight, FiCheck, FiChevronDown, FiChevronUp } from 'react-icons/fi';

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

const formatValue = (value: any): string => {
  if (value === null || value === undefined) return '-';
  return String(value);
};

const SourcingAgent: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const state = (location.state as any) ?? {};
  const parsed = state.parsedResult ?? null;

  // Sourcing parameters
  const sourcingFromState = state.sourcing ?? null;
  const derivedSourcingFromParsed = parsed?.criteria?.mandate?.sourcing_parameters ?? parsed?.criteria?.fund_mandate?.sourcing_parameters ?? null;
  const sourcingList = sourcingFromState ?? toDisplayArray(derivedSourcingFromParsed);

  // Screening parameters
  const screeningFromState = state.screening ?? null;
  const derivedScreeningFromParsed = parsed?.criteria?.mandate?.screening_parameters ?? parsed?.criteria?.fund_mandate?.screening_parameters ?? null;
  const screeningList = screeningFromState ?? toDisplayArray(derivedScreeningFromParsed);

  // Risk analysis parameters
  const riskAnalysisFromState = state.riskAnalysis ?? null;
  const derivedRiskAnalysisFromParsed = parsed?.criteria?.mandate?.risk_analysis_parameters ?? parsed?.criteria?.fund_mandate?.risk_analysis_parameters ?? null;
  const riskAnalysisList = riskAnalysisFromState ?? toDisplayArray(derivedRiskAnalysisFromParsed);

  // Step management
  const [currentStep, setCurrentStep] = useState(0);

  const [selectedSourcingKeys, setSelectedSourcingKeys] = useState<Record<string, boolean>>({});
  const [selectedScreeningKeys, setSelectedScreeningKeys] = useState<Record<string, boolean>>({});
  const [selectedRiskAnalysisKeys, setSelectedRiskAnalysisKeys] = useState<Record<string, boolean>>({});
  const [selectedCompanies, setSelectedCompanies] = useState<Record<number, boolean>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [filterResponse, setFilterResponse] = useState<any>(null);
  const [screeningResponse, setScreeningResponse] = useState<any>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    sourcing: true,
    screening: true,
    riskAnalysis: true,
  });

  const toggleSourcingSelect = (key: string) => {
    setSelectedSourcingKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleScreeningSelect = (key: string) => {
    setSelectedScreeningKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleRiskAnalysisSelect = (key: string) => {
    setSelectedRiskAnalysisKeys((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const toggleCompanySelect = (index: number) => {
    setSelectedCompanies((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const getSelectedSourcingItems = () => sourcingList.filter((s: any) => selectedSourcingKeys[s.key]);
  const getSelectedScreeningItems = () => screeningList.filter((s: any) => selectedScreeningKeys[s.key]);
  const getSelectedRiskAnalysisItems = () => riskAnalysisList.filter((r: any) => selectedRiskAnalysisKeys[r.key]);
  const getSelectedCompanyList = () => {
    if (!filterResponse?.companies?.qualified) return [];
    return filterResponse.companies.qualified.filter((_: any, index: number) => selectedCompanies[index]);
  };

  const canProceedStep = () => {
    switch (currentStep) {
      case 0:
        return filterResponse && filterResponse.companies && filterResponse.companies.qualified && filterResponse.companies.qualified.length > 0;
      case 1:
        return screeningResponse && screeningResponse.company_details && screeningResponse.company_details.length > 0;
      case 2:
        return true;
      default:
        return false;
    }
  };

  const nextStep = () => {
    if (canProceedStep() && currentStep < 2) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleSourceCompanies = async () => {
    const items = getSelectedSourcingItems();
    if (!items || items.length === 0) {
      toast.error('Please select at least one sourcing threshold to continue');
      return;
    }

    setIsSubmitting(true);
    setFilterResponse(null);

    try {
      const selectedParams: Record<string, string> = {};
      items.forEach((item: any) => {
        selectedParams[item.key.toLowerCase().replace(/\s+/g, '_')] = item.value;
      });

      const payload = {
        additionalProp1: selectedParams
      };

      console.log('Sourcing payload:', payload);

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
      setFilterResponse(data);
      toast.success('Companies sourced successfully');
    } catch (err) {
      console.error('Error sourcing companies:', err);
      toast.error('Failed to source companies');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleScreenCompanies = async () => {
    const selectedScreeningItems = getSelectedScreeningItems();
    const selectedCompanyList = getSelectedCompanyList();

    if (!selectedScreeningItems || selectedScreeningItems.length === 0) {
      toast.error('Please select at least one screening parameter');
      return;
    }

    if (!selectedCompanyList || selectedCompanyList.length === 0) {
      toast.error('Please select at least one company to screen');
      return;
    }

    setIsSubmitting(true);
    setScreeningResponse(null);

    try {
      // Build mandate_parameters from selected screening items
      const mandateParameters: Record<string, string> = {};
      selectedScreeningItems.forEach((item: any) => {
        mandateParameters[item.key.toLowerCase().replace(/\s+/g, '_')] = item.value;
      });

      const payload = {
        mandate_parameters: mandateParameters,
        companies: selectedCompanyList
      };

      console.log('Screening payload:', payload);

      const resp = await fetch(`${API.BASE_URL()}/api/screen-companies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(txt || `Server error ${resp.status}`);
      }

      const data = await resp.json();
      console.log('Screening response:', data);
      setScreeningResponse(data);
      toast.success('Companies screened successfully');
    } catch (err) {
      console.error('Error screening companies:', err);
      toast.error('Failed to screen companies');
    } finally {
      setIsSubmitting(false);
    }
  };

  const stepTitles = ['Sourcing', 'Screening', 'Risk Analysis'];

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-6">
            {sourcingList && sourcingList.length > 0 ? (
              <>
                <button
                  onClick={() => toggleSection('sourcing')}
                  className="flex items-center gap-3 hover:text-gray-700 transition-colors group"
                >
                  {openSections.sourcing ? (
                    <FiChevronUp className="w-5 h-5 text-gray-600 group-hover:text-gray-800" />
                  ) : (
                    <FiChevronDown className="w-5 h-5 text-gray-600 group-hover:text-gray-800" />
                  )}
                  <h3 className="text-sm font-semibold text-gray-700">Sourcing Parameters</h3>
                </button>
                {openSections.sourcing && (
                  <div className="grid grid-cols-3 gap-6 mt-4">
                    {sourcingList.map((threshold: any) => {
                      const selected = !!selectedSourcingKeys[threshold.key];
                      return (
                        <label
                          key={threshold.key}
                          className="flex items-start gap-3 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleSourcingSelect(threshold.key)}
                            className="w-4 h-4 mt-1 text-indigo-600 rounded"
                          />
                          <div className="flex-1">
                            <span className="text-sm font-medium text-gray-800">{threshold.key}</span>
                            <div className="text-xs text-gray-600 mt-1">{threshold.value}</div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}

                {filterResponse?.companies?.qualified ? (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">Sourced Companies</h3>
                    <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                      <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                        <table className="w-full">
                          <thead className="sticky top-0 z-10">
                            <tr className="bg-[#BEBEBE]">
                              <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">S.No.</th>
                              <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">Company</th>
                              {filterResponse.companies.qualified[0] &&
                                Object.keys(filterResponse.companies.qualified[0]).map((col) => (
                                  col !== 'Company ' && (
                                    <th
                                      key={col}
                                      className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center"
                                    >
                                      {col}
                                    </th>
                                  )
                                ))}
                            </tr>
                          </thead>
                          <tbody>
                            {filterResponse.companies.qualified.map((row: any, index: number) => (
                              <tr key={index} className="hover:bg-indigo-50 transition-colors">
                                <td className="px-3 py-3 text-sm text-black">{index + 1}.</td>
                                <td className="px-3 py-3 text-sm text-indigo-600 font-bold whitespace-nowrap">{row['Company '] || row['Company']}</td>
                                {Object.entries(row).map(([col, value]: [string, any]) => {
                                  if (col === 'Company ' || col === 'Company') return null;
                                  return (
                                    <td key={col} className="px-3 py-3 text-sm text-black whitespace-nowrap text-center">
                                      {formatValue(value)}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    <p className="text-xs text-gray-600 mt-3">
                      {filterResponse.companies.qualified.length} companies qualified based on sourcing criteria
                    </p>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-gray-600">No sourcing parameters found. Navigate from Fund Mandate after upload.</p>
            )}
          </div>
        );

      case 1:
        return (
          <div className="space-y-4">
            {filterResponse?.companies?.qualified ? (
              <>
                <div className="pb-4">
                  <p className="text-sm text-black-800">
                    <strong>Step 2:</strong> Select screening parameters and companies to screen. Click "Screen Companies" to apply the selected criteria.
                  </p>
                </div>

                {screeningList && screeningList.length > 0 && (
                  <>
                    <button
                      onClick={() => toggleSection('screening')}
                      className="flex items-center gap-3 hover:text-gray-700 transition-colors group"
                    >
                      {openSections.screening ? (
                        <FiChevronUp className="w-5 h-5 text-gray-600 group-hover:text-gray-800" />
                      ) : (
                        <FiChevronDown className="w-5 h-5 text-gray-600 group-hover:text-gray-800" />
                      )}
                      <h3 className="text-sm font-semibold text-gray-700">Screening Parameters</h3>
                    </button>
                    {openSections.screening && (
                      <div className="grid grid-cols-3 gap-6 mt-4">
                        {screeningList.map((param: any) => {
                          const selected = !!selectedScreeningKeys[param.key];
                          return (
                            <label
                              key={param.key}
                              className="flex items-start gap-3 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={selected}
                                onChange={() => toggleScreeningSelect(param.key)}
                                className="w-4 h-4 mt-1 text-indigo-600 rounded"
                              />
                              <div className="flex-1">
                                <span className="text-sm font-medium text-gray-800">{param.key}</span>
                                <div className="text-xs text-gray-600 mt-1">{param.value}</div>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}

                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-4">Select Companies to Screen</h3>
                  <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                    <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                      <table className="w-full">
                        <thead className="sticky top-0 z-10">
                          <tr className="bg-[#BEBEBE]">
                            <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">
                              <input
                                type="checkbox"
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    const newSelected: Record<number, boolean> = {};
                                    filterResponse.companies.qualified.forEach((_: any, idx: number) => {
                                      newSelected[idx] = true;
                                    });
                                    setSelectedCompanies(newSelected);
                                  } else {
                                    setSelectedCompanies({});
                                  }
                                }}
                                className="w-4 h-4 text-indigo-600 rounded"
                              />
                            </th>
                            <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">Company</th>
                            {filterResponse.companies.qualified[0] &&
                              Object.keys(filterResponse.companies.qualified[0]).map((col) => (
                                col !== 'Company ' && (
                                  <th
                                    key={col}
                                    className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center"
                                  >
                                    {col}
                                  </th>
                                )
                              ))}
                          </tr>
                        </thead>
                        <tbody>
                          {filterResponse.companies.qualified.map((row: any, index: number) => {
                            const isSelected = !!selectedCompanies[index];
                            return (
                              <tr key={index} className={`${isSelected ? 'bg-indigo-50' : 'hover:bg-gray-50'} transition-colors cursor-pointer`}>
                                <td className="px-3 py-3 text-sm text-black">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => toggleCompanySelect(index)}
                                    className="w-4 h-4 text-indigo-600 rounded"
                                  />
                                </td>
                                <td className="px-3 py-3 text-sm text-indigo-600 font-bold whitespace-nowrap">{row['Company '] || row['Company']}</td>
                                {Object.entries(row).map(([col, value]: [string, any]) => {
                                  if (col === 'Company ' || col === 'Company') return null;
                                  return (
                                    <td key={col} className="px-3 py-3 text-sm text-black whitespace-nowrap text-center">
                                      {formatValue(value)}
                                    </td>
                                  );
                                })}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {screeningResponse?.company_details ? (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">Screening Results</h3>
                    <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                      <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                        <table className="w-full">
                          <thead className="sticky top-0 z-10">
                            <tr className="bg-[#BEBEBE]">
                              <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">S.No.</th>
                              {screeningResponse.company_details[0] &&
                                Object.keys(screeningResponse.company_details[0]).map((col) => (
                                  <th
                                    key={col}
                                    className={`px-3 py-3 text-xs font-bold text-black whitespace-nowrap ${col === 'Company ' || col === 'Company' ? 'text-left' : 'text-center'}`}
                                  >
                                    {col}
                                  </th>
                                ))}
                            </tr>
                          </thead>
                          <tbody>
                            {screeningResponse.company_details.map((row: any, index: number) => (
                              <tr key={index} className="hover:bg-indigo-50 transition-colors">
                                <td className="px-3 py-3 text-sm text-black">{index + 1}.</td>
                                {Object.entries(row).map(([col, value]: [string, any]) => (
                                  <td
                                    key={col}
                                    className={`px-3 py-3 text-sm whitespace-nowrap ${
                                      col === 'Company ' || col === 'Company'
                                        ? 'text-left text-indigo-600 font-bold'
                                        : 'text-center text-black'
                                    }`}
                                  >
                                    {formatValue(value)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                    <p className="text-xs text-gray-600 mt-3">
                      {screeningResponse.company_details.length} companies passed screening criteria
                    </p>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="bg-gray-50 rounded-lg p-6 text-center">
                <p className="text-sm text-gray-600">Please complete Step 1 (Sourcing) first</p>
              </div>
            )}
          </div>
        );

      case 2:
        return (
          <div className="space-y-6">
            {screeningResponse?.company_details && screeningResponse.company_details.length > 0 ? (
              <>
                <div className="bg-green-50 rounded-lg p-4 border border-green-200">
                  <h3 className="text-lg font-semibold text-green-900 mb-2">Screening Complete!</h3>
                  <p className="text-sm text-green-800">
                    {screeningResponse.company_details.length} companies have passed the screening criteria.
                  </p>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-4">Final Screening Results</h3>
                  <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                    <div className="overflow-x-auto overflow-y-auto max-h-[500px]">
                      <table className="w-full">
                        <thead className="sticky top-0 z-10">
                          <tr className="bg-[#BEBEBE]">
                            <th className="px-3 py-3 text-left text-xs font-bold text-black whitespace-nowrap">S.No.</th>
                            {screeningResponse.company_details[0] &&
                              Object.keys(screeningResponse.company_details[0]).map((col) => (
                                <th
                                  key={col}
                                  className={`px-3 py-3 text-xs font-bold text-black whitespace-nowrap ${col === 'Company ' || col === 'Company' ? 'text-left' : 'text-center'}`}
                                >
                                  {col}
                                </th>
                              ))}
                          </tr>
                        </thead>
                        <tbody>
                          {screeningResponse.company_details.map((row: any, index: number) => (
                            <tr key={index} className="hover:bg-indigo-50 transition-colors">
                              <td className="px-3 py-3 text-sm text-black">{index + 1}.</td>
                              {Object.entries(row).map(([col, value]: [string, any]) => (
                                <td
                                  key={col}
                                  className={`px-3 py-3 text-sm whitespace-nowrap ${
                                    col === 'Company ' || col === 'Company'
                                      ? 'text-left text-indigo-600 font-bold'
                                      : 'text-center text-black'
                                  }`}
                                >
                                  {formatValue(value)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {riskAnalysisList && riskAnalysisList.length > 0 ? (
                  <>
                    <button
                      onClick={() => toggleSection('riskAnalysis')}
                      className="flex items-center gap-3 hover:text-gray-700 transition-colors group"
                    >
                      {openSections.riskAnalysis ? (
                        <FiChevronUp className="w-5 h-5 text-gray-600 group-hover:text-gray-800" />
                      ) : (
                        <FiChevronDown className="w-5 h-5 text-gray-600 group-hover:text-gray-800" />
                      )}
                      <h3 className="text-sm font-semibold text-gray-700">Risk Analysis Parameters</h3>
                    </button>
                    {openSections.riskAnalysis && (
                      <div className="grid grid-cols-3 gap-6 mt-4">
                        {riskAnalysisList.map((param: any) => {
                          const selected = !!selectedRiskAnalysisKeys[param.key];
                          return (
                            <label
                              key={param.key}
                              className="flex items-start gap-3 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={selected}
                                onChange={() => toggleRiskAnalysisSelect(param.key)}
                                className="w-4 h-4 mt-1 text-indigo-600 rounded"
                              />
                              <div className="flex-1">
                                <span className="text-sm font-medium text-gray-800">{param.key}</span>
                                <div className="text-xs text-gray-600 mt-1">{param.value}</div>
                              </div>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <p className="text-sm text-blue-800">
                      <strong>Next Steps:</strong> No risk analysis parameters available. You can now review the screening results or export this data.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-gray-50 rounded-lg p-6 text-center">
                <p className="text-sm text-gray-600">Please complete Step 2 (Screening) first</p>
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };
  return (
    <div className="flex flex-col min-h-full bg-gray-50">
      {/* Header */}
      <header className="border-b sticky top-0 bg-background/95 bg-white z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div>
                <h1 className="text-xl font-bold">Sourcing & Screening Agent</h1>
                <p className="text-xs text-muted-foreground">
                  Select parameters, source companies, and apply screening criteria
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-8 py-8">
          <div className="max-w-6xl mx-auto">

          {/* Wizard Steps */}
          <div className="mb-8">
            <div className="flex items-center space-x-4">
              {stepTitles.map((title, index) => (
                <div key={index} className="flex items-center">
                  <div
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200 ${
                      index === currentStep
                        ? 'bg-primary text-white'
                        : 'bg-white text-gray-600 border border-gray-200'
                    }`}
                  >
                    <div
                      className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                        index === currentStep
                          ? 'bg-white text-primary'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {index + 1}
                    </div>
                    <span className="text-sm font-medium">{title}</span>
                  </div>
                  {index < stepTitles.length - 1 && (
                    <FiArrowRight className="w-4 h-4 text-gray-400 mx-2" />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Step Content */}
          <div className="p-8 mb-8">
            {renderStepContent()}
          </div>

          {/* Navigation Buttons */}
          <div className="flex justify-between">
            {currentStep > 0 && (
              <button
                onClick={prevStep}
                className="flex items-center space-x-2 px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <FiArrowLeft className="w-4 h-4" />
                <span>Back</span>
              </button>
            )}

            <div className="flex items-center space-x-4 ml-auto">
              {currentStep === 0 && (
                <button
                  onClick={filterResponse ? nextStep : handleSourceCompanies}
                  disabled={isSubmitting || (filterResponse ? false : getSelectedSourcingItems().length === 0)}
                  className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-colors ${
                    isSubmitting || (filterResponse ? false : getSelectedSourcingItems().length === 0)
                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                      : 'bg-indigo-600 text-white hover:bg-indigo-700'
                  }`}
                >
                  {isSubmitting ? (
                    <span>Sourcing...</span>
                  ) : filterResponse ? (
                    <>
                      <span>Next</span>
                      <FiArrowRight className="w-4 h-4" />
                    </>
                  ) : (
                    <span>Source Companies</span>
                  )}
                </button>
              )}

              {currentStep === 1 && (
                <button
                  onClick={screeningResponse ? nextStep : handleScreenCompanies}
                  disabled={isSubmitting || (screeningResponse ? false : (getSelectedScreeningItems().length === 0 || getSelectedCompanyList().length === 0))}
                  className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-colors ${
                    isSubmitting || (screeningResponse ? false : (getSelectedScreeningItems().length === 0 || getSelectedCompanyList().length === 0))
                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                      : 'bg-indigo-600 text-white hover:bg-indigo-700'
                  }`}
                >
                  {isSubmitting ? (
                    <span>Screening...</span>
                  ) : screeningResponse ? (
                    <>
                      <span>Next</span>
                      <FiArrowRight className="w-4 h-4" />
                    </>
                  ) : (
                    <span>Screen Companies</span>
                  )}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};

export default SourcingAgent;
