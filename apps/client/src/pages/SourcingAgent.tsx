import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { API } from '../utils/constants';
import { Dialog,DialogTitle,DialogContent,DialogActions,Button,Skeleton } from "@mui/material"
import toast from 'react-hot-toast';
import { FiArrowLeft, FiArrowRight, FiChevronDown, FiChevronLeft, FiChevronRight, FiChevronUp, FiMessageSquare, FiEye } from 'react-icons/fi';

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
  const location = useLocation();

  const state = (location.state as any) ?? {};
  const parsed = state.parsedResult ?? null;

  // Sourcing parameters - use from state first, then fall back to parsed data
  const sourcingFromState = state.sourcing ?? null;
  const derivedSourcingFromParsed =
    parsed?.criteria?.mandate?.sourcing_parameters ??
    parsed?.criteria?.fund_mandate?.sourcing_parameters ??
    parsed?.criteria?.sourcing_parameters ??
    parsed?.sourcing_parameters ??
    null;
  const sourcingList = sourcingFromState ?? toDisplayArray(derivedSourcingFromParsed);

  // Screening parameters - use from state first, then fall back to parsed data
  const screeningFromState = state.screening ?? null;
  const derivedScreeningFromParsed =
    parsed?.criteria?.mandate?.screening_parameters ??
    parsed?.criteria?.fund_mandate?.screening_parameters ??
    parsed?.criteria?.screening_parameters ??
    parsed?.screening_parameters ??
    null;
  const screeningList = screeningFromState ?? toDisplayArray(derivedScreeningFromParsed);

  // Risk analysis parameters - use from state first, then fall back to parsed data
  const riskAnalysisFromState = state.riskAnalysis ?? null;
  const derivedRiskAnalysisFromParsed =
    parsed?.criteria?.mandate?.risk_parameters ??
    parsed?.criteria?.fund_mandate?.risk_parameters ??
    parsed?.criteria?.risk_parameters ??
    parsed?.risk_parameters ??
    null;
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
  const [riskAnalysisResponse, setRiskAnalysisResponse] = useState<any>(null);
  const [expandedScreeningResults, setExpandedScreeningResults] = useState<Record<number, boolean>>({});
  const [companyDetailOpen, setCompanyDetailOpen] = useState(false);
  const [selectedCompanyDetail, setSelectedCompanyDetail] = useState<any>(null);
  const screeningResultsRef = useRef<HTMLDivElement>(null);
  const riskAnalysisResultsRef = useRef<HTMLDivElement>(null);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    sourcing: true,
    screening: true,
    riskAnalysis: true,
  });
  const [agentThinkingOpen, setAgentThinkingOpen] = useState(true);
  const [streamingEvents, setStreamingEvents] = useState<any[]>([]);
  const [showStreamingPanel, setShowStreamingPanel] = useState(false);
  const streamingPanelRef = useRef<HTMLDivElement>(null);

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

  const toggleScreeningResult = (index: number) => {
    setExpandedScreeningResults((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const openCompanyDetail = (company: any) => {
    setSelectedCompanyDetail(company);
    setCompanyDetailOpen(true);
  };

  const closeCompanyDetail = () => {
    setCompanyDetailOpen(false);
    setSelectedCompanyDetail(null);
  };

  // Auto-select all parameters by default
  useEffect(() => {
    if (sourcingList.length > 0) {
      const selectedKeys: Record<string, boolean> = {};
      sourcingList.forEach((item: any) => {
        selectedKeys[item.key] = true;
      });
      setSelectedSourcingKeys(selectedKeys);
    }
  }, [sourcingList]);

  useEffect(() => {
    if (screeningList.length > 0) {
      const selectedKeys: Record<string, boolean> = {};
      screeningList.forEach((item: any) => {
        selectedKeys[item.key] = true;
      });
      setSelectedScreeningKeys(selectedKeys);
    }
  }, [screeningList]);

  useEffect(() => {
    if (riskAnalysisList.length > 0) {
      const selectedKeys: Record<string, boolean> = {};
      riskAnalysisList.forEach((item: any) => {
        selectedKeys[item.key] = true;
      });
      setSelectedRiskAnalysisKeys(selectedKeys);
    }
  }, [riskAnalysisList]);

  useEffect(() => {
    if (riskAnalysisResponse?.investable_companies && riskAnalysisResultsRef.current) {
      riskAnalysisResultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [riskAnalysisResponse]);

  useEffect(() => {
    if (streamingPanelRef.current && streamingEvents.length > 0) {
      streamingPanelRef.current.scrollTop = streamingPanelRef.current.scrollHeight;
    }
  }, [streamingEvents]);

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
      // Clear streaming events when navigating to next step
      setStreamingEvents([]);
      setShowStreamingPanel(false);
      setCurrentStep((prev) => prev + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      // Clear streaming events when navigating back
      setStreamingEvents([]);
      setShowStreamingPanel(false);
      setCurrentStep((prev) => prev - 1);
    }
  };

  const resetScreening = () => {
    setScreeningResponse(null);
    setExpandedScreeningResults({});
    setSelectedCompanies({});
  };

  const resetRiskAnalysis = () => {
    setRiskAnalysisResponse(null);
  };

  const handleSourceCompanies = async () => {
    const items = getSelectedSourcingItems();
    if (!items || items.length === 0) {
      toast.error('Please select at least one sourcing threshold to continue');
      return;
    }

    setIsSubmitting(true);
    setFilterResponse(null);
    setStreamingEvents([]);
    setShowStreamingPanel(true);

    try {
      const selectedParams: Record<string, string> = {};
      items.forEach((item: any) => {
        selectedParams[item.key.toLowerCase().replace(/\s+/g, '_')] = item.value;
      });

      const payload = {
        additionalProp1: selectedParams
      };

      console.log('Sourcing payload:', payload);

      // Create WebSocket connection
      const connId = `sourcing-${Date.now()}`;
      const wsUrl = API.wsUrl(API.ENDPOINTS.FILTER.FILTER_COMPANIES_WS(connId));
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('Sourcing WebSocket connected');
        ws.send(JSON.stringify(payload));
      };

      ws.onmessage = (event) => {
        const eventData = JSON.parse(event.data);
        console.log('Sourcing event:', eventData);
        setStreamingEvents((prev) => [...prev, eventData]);

        // Handle analysis_complete event
        if (eventData.type === 'analysis_complete' && eventData.result) {
          console.log('Sourcing complete, result:', eventData.result);

          // Transform response to match expected structure (companies.qualified)
          const transformedResponse = {
            companies: {
              qualified: eventData.result.qualified || []
            }
          };

          setFilterResponse(transformedResponse);
          setShowStreamingPanel(false);
          toast.success(`${eventData.result.qualified?.length || 0} companies sourced successfully`);
          ws.close();
        }
      };

      ws.onerror = (error) => {
        console.error('Sourcing WebSocket error:', error);
        toast.error('WebSocket error during sourcing');
        setShowStreamingPanel(false);
      };

      ws.onclose = () => {
        console.log('Sourcing WebSocket closed');
        setIsSubmitting(false);
      };
    } catch (err) {
      console.error('Error sourcing companies:', err);
      toast.error('Failed to source companies');
      setShowStreamingPanel(false);
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
    setStreamingEvents([]);
    setShowStreamingPanel(true);

    // Collect agent thinking events during screening
    const agentThinkingSteps: string[] = [];

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

      // Create WebSocket connection
      const wsUrl = API.wsUrl(API.ENDPOINTS.FILTER.SCREEN_WS());
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('Screening WebSocket connected');
        ws.send(JSON.stringify(payload));
      };

      ws.onmessage = (event) => {
        const eventData = JSON.parse(event.data);
        console.log('Screening event:', eventData);
        setStreamingEvents((prev) => [...prev, eventData]);

        // Collect agent thinking events (step_2 and other thinking-related events)
        if (eventData.type && eventData.content) {
          // Extract thinking content from various step types
          const content = eventData.content || '';
          if (content && typeof content === 'string') {
            // Clean up the content - remove emoji prefixes and step labels
            const cleanContent = content
              .replace(/^[âœ…ðŸ’­ðŸ”§âš™ï¸âœ¨ðŸ“‹â³ðŸ“ŠðŸ¤–]\s*/g, '')
              .replace(/^STEP \d+:\s*/i, '')
              .trim();
            if (cleanContent) {
              agentThinkingSteps.push(cleanContent);
            }
          }
        }

        // Handle final_result event
        if (eventData.type === 'final_result' && eventData.content) {
          console.log('Screening complete, result:', eventData.content);
          // Include agent_thinking in the response
          const responseWithThinking = {
            ...eventData.content,
            agent_thinking: agentThinkingSteps
          };
          setScreeningResponse(responseWithThinking);
          setShowStreamingPanel(false);
          toast.success('Companies screened successfully');
          ws.close();
          setTimeout(() => {
            screeningResultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }, 100);
        }
      };

      ws.onerror = (error) => {
        console.error('Screening WebSocket error:', error);
        toast.error('WebSocket error during screening');
        setShowStreamingPanel(false);
      };

      ws.onclose = () => {
        console.log('Screening WebSocket closed');
        setIsSubmitting(false);
      };
    } catch (err) {
      console.error('Error screening companies:', err);
      toast.error('Failed to screen companies');
      setShowStreamingPanel(false);
      setIsSubmitting(false);
    }
  };

  const handleAnalyzeRisk = async () => {
    const selectedRiskItems = getSelectedRiskAnalysisItems();

    if (!selectedRiskItems || selectedRiskItems.length === 0) {
      toast.error('Please select at least one risk analysis parameter');
      return;
    }

    if (!screeningResponse?.company_details || screeningResponse.company_details.length === 0) {
      toast.error('No companies available for risk analysis');
      return;
    }

    setIsSubmitting(true);
    setRiskAnalysisResponse(null);
    setStreamingEvents([]);
    setShowStreamingPanel(true);

    try {
      // Build risk_parameters from selected risk analysis items
      const riskParameters: Record<string, string> = {};
      selectedRiskItems.forEach((item: any) => {
        riskParameters[item.key] = item.value;
      });

      // Get companies from screening response
      const companies = screeningResponse.company_details;

      const payload = {
        companies: companies,
        risk_parameters: riskParameters
      };

      console.log('Risk analysis payload:', payload);

      // Connect to WebSocket endpoint
      const wsUrl = API.wsUrl(API.ENDPOINTS.RISK.ANALYZE_STREAM());

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('âœ… WebSocket connected');
        // Send the analysis request
        ws.send(JSON.stringify(payload));
      };

      ws.onmessage = (event) => {
        try {
          const eventData = JSON.parse(event.data);
          console.log('ðŸ“¨ Received event:', eventData);

          // Add event to streaming events
          setStreamingEvents((prev) => [...prev, eventData]);

          // Handle session_complete to extract final results and transform into table-friendly format
          if (eventData.type === 'session_complete' && eventData.results) {
            try {
              const transformedCompanies = (eventData.results || []).map((c: any) => {
                const pa = c.parameter_analysis || c.parameterAnalysis || {};
                const risk_scores = Object.entries(pa).map(([category, val]: [string, any]) => {
                  const statusStr = String(val?.status ?? val?.Status ?? val?.status_text ?? '').toUpperCase();
                  return {
                    category,
                    status: val?.status ?? val?.Status ?? val?.status_text ?? statusStr,
                    reason: (val && (val.reason || val.Reason || val?.reason_text)) || ''
                  };
                });

                return {
                  company_name: c.company_name || c.Company || c.company || 'Unknown',
                  risk_scores,
                  overall_status: c.overall_assessment || c.overall_result || c.overall_status || c.overallStatus || c.overall || ''
                };
              });

              const transformedResults = {
                all_companies: transformedCompanies,
                summary: {
                  total: transformedCompanies.length,
                  passed: transformedCompanies.filter((r: any) => String(r.overall_status).toUpperCase() === 'SAFE').length
                }
              };

              setRiskAnalysisResponse(transformedResults);
              toast.success('Risk analysis completed successfully');
              // Close WebSocket and hide processing indicator after session_complete
              setShowStreamingPanel(false);
              ws.close();
            } catch (e) {
              console.error('Error transforming session_complete results', e);
            }
          }

          // Scroll streaming panel to bottom
          setTimeout(() => {
            if (streamingPanelRef.current) {
              streamingPanelRef.current.scrollTop = streamingPanelRef.current.scrollHeight;
            }
          }, 0);
        } catch (err) {
          console.error('Error parsing event:', err);
        }
      };

      ws.onerror = (error) => {
        console.error(' WebSocket error:', error);
        toast.error('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log(' WebSocket closed');
        setIsSubmitting(false);
      };
    } catch (err) {
      console.error('Error analyzing risk:', err);
      toast.error('Failed to analyze risk');
      setIsSubmitting(false);
    }
  };

  const exportRiskAnalysisToCSV = () => {
    if (!riskAnalysisResponse?.all_companies) {
      toast.error('No data to export');
      return;
    }

    try {
      // Prepare CSV headers
      const headers = ['S.No.', 'Company Name', 'Overall Status', 'Category', 'Status', 'Reason'];

      // Prepare CSV rows
      const rows: string[][] = [];
      let rowNumber = 1;

      riskAnalysisResponse.all_companies.forEach((company: any, companyIndex: number) => {
        company.risk_scores?.forEach((risk: any, riskIndex: number) => {
          rows.push([
            String(rowNumber++),
            company.company_name,
            company.overall_status ?? '',
            risk.category,
            risk.status ?? '',
            risk.reason ?? ''
          ]);
        });
      });

      // Escape CSV values (handle commas and quotes)
      const escapeCSV = (value: string) => {
        if (value.includes(',') || value.includes('"') || value.includes('\n')) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      };

      // Build CSV content
      const csvContent = [
        headers.map(escapeCSV).join(','),
        ...rows.map(row => row.map(escapeCSV).join(','))
      ].join('\n');

      // Create blob and download
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);

      const timestamp = new Date().toISOString().slice(0, 10);
      link.setAttribute('href', url);
      link.setAttribute('download', `risk-analysis-${timestamp}.csv`);
      link.style.visibility = 'hidden';

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      toast.success('Risk analysis data exported to CSV');
    } catch (err) {
      console.error('Error exporting CSV:', err);
      toast.error('Failed to export CSV');
    }
  };

  const stepTitles = ['Sourcing', 'Screening', 'Risk Analysis'];

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-6">
           <div className="pb-4">
                  <p className="text-sm text-black-800">
                    <strong>Step 1:</strong> Select the necessary sourcing parameters.
                  </p>
                </div>
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

                {isSubmitting && !filterResponse ? (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">Sourced Companies</h3>
                    <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                      <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                        <table className="w-full">
                          <thead className="sticky top-0 z-10">
                            <tr className="bg-[#BEBEBE]">
                              <th className="px-2 py-3 text-left text-xs font-bold text-black w-12">S.No.</th>
                              <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[150px] max-w-[200px]">Company</th>
                              <th className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center">Attribute 1</th>
                              <th className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center">Attribute 2</th>
                              <th className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center">Attribute 3</th>
                              <th className="px-3 py-3 text-center text-xs font-bold text-black whitespace-nowrap">View</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[1, 2, 3, 4, 5].map((i) => (
                              <tr key={i} className="hover:bg-indigo-50 transition-colors">
                                <td className="px-2 py-3 text-sm text-black w-12"><Skeleton width="20px" height="20px" /></td>
                                <td className="px-3 py-3 text-sm"><Skeleton width="100%" height="20px" /></td>
                                <td className="px-3 py-3 text-sm text-center"><Skeleton width="80%" height="20px" /></td>
                                <td className="px-3 py-3 text-sm text-center"><Skeleton width="80%" height="20px" /></td>
                                <td className="px-3 py-3 text-sm text-center"><Skeleton width="80%" height="20px" /></td>
                                <td className="px-3 py-3 text-sm text-center"><Skeleton width="30px" height="30px" sx={{ borderRadius: '50%' }} /></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ) : null}

                {filterResponse?.companies?.qualified ? (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-4">Sourced Companies</h3>
                    <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                      <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                        <table className="w-full">
                          <thead className="sticky top-0 z-10">
                            <tr className="bg-[#BEBEBE]">
                              <th className="px-2 py-3 text-left text-xs font-bold text-black w-12">S.No.</th>
                              <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[150px] max-w-[200px]">Company</th>
                              {filterResponse.companies.qualified[0] &&
                                Object.keys(filterResponse.companies.qualified[0])
                                  .filter((col) => col !== 'Company ' && col !== 'Company')
                                  .slice(0, 3)
                                  .map((col) => (
                                    <th
                                      key={col}
                                      className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center"
                                    >
                                      {col}
                                    </th>
                                  ))}
                              <th className="px-3 py-3 text-center text-xs font-bold text-black whitespace-nowrap">View</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filterResponse.companies.qualified.map((row: any, index: number) => {
                              const columns = Object.entries(row).filter(([col]) => col !== 'Company ' && col !== 'Company');
                              return (
                                <tr key={index} className="hover:bg-indigo-50 transition-colors">
                                  <td className="px-2 py-3 text-sm text-black w-12">{index + 1}.</td>
                                  <td className="px-3 py-3 text-sm text-indigo-600 font-bold min-w-[150px] max-w-[200px] break-words">{row['Company '] || row['Company']}</td>
                                  {columns.slice(0, 3).map(([col, value]: [string, any]) => (
                                    <td key={col} className="px-3 py-3 text-sm text-black whitespace-nowrap text-center">
                                      {formatValue(value)}
                                    </td>
                                  ))}
                                  <td className="px-3 py-3 text-sm text-center">
                                    <button
                                      onClick={() => openCompanyDetail(row)}
                                      className="text-indigo-600 hover:text-indigo-800 transition-colors"
                                    >
                                      <FiEye className="w-5 h-5" />
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
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
          <div className="space-y-6">
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

                <div className="mb-8">
                  <h3 className="text-sm font-semibold text-gray-700 mb-4">Select Companies to Screen</h3>
                  <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                    <div className="overflow-x-auto overflow-y-auto max-h-[400px]">
                      <table className="w-full">
                        <thead className="sticky top-0 z-10">
                          <tr className="bg-[#BEBEBE]">
                            <th className="px-2 py-3 text-left text-xs font-bold text-black w-12">
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
                            <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[150px] max-w-[200px]">Company</th>
                            {filterResponse.companies.qualified[0] &&
                              Object.keys(filterResponse.companies.qualified[0])
                                .filter((col) => col !== 'Company ' && col !== 'Company')
                                .slice(0, 4)
                                .map((col) => (
                                  <th
                                    key={col}
                                    className="px-3 py-3 text-xs font-bold text-black whitespace-nowrap text-center"
                                  >
                                    {col}
                                  </th>
                                ))}
                            <th className="px-3 py-3 text-center text-xs font-bold text-black whitespace-nowrap">View</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filterResponse.companies.qualified.map((row: any, index: number) => {
                            const isSelected = !!selectedCompanies[index];
                            const columns = Object.entries(row).filter(([col]) => col !== 'Company ' && col !== 'Company');
                            return (
                              <tr key={index} className={`${isSelected ? 'bg-indigo-50' : 'hover:bg-gray-50'} transition-colors cursor-pointer`}>
                                <td className="px-2 py-3 text-sm text-black w-12">
                                  <input
                                    type="checkbox"
                                    checked={isSelected}
                                    onChange={() => toggleCompanySelect(index)}
                                    className="w-4 h-4 text-indigo-600 rounded"
                                  />
                                </td>
                                <td className="px-3 py-3 text-sm text-indigo-600 font-bold min-w-[150px] max-w-[200px] break-words">{row['Company '] || row['Company']}</td>
                                {columns.slice(0, 4).map(([col, value]: [string, any]) => (
                                  <td key={col} className="px-3 py-3 text-sm text-black whitespace-nowrap text-center">
                                    {formatValue(value)}
                                  </td>
                                ))}
                                <td className="px-3 py-3 text-sm text-center">
                                  <button
                                    onClick={() => openCompanyDetail(row)}
                                    className="text-indigo-600 hover:text-indigo-800 transition-colors"
                                  >
                                    <FiEye className="w-5 h-5" />
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>

                {isSubmitting && !screeningResponse ? (
                  <div className="mt-12">
                    <h3 className="text-base font-bold text-black">List of companies passed the criteria</h3>
                    <p className="text-sm text-black mb-4">Loading screening results...</p>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                      {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} className="p-2 bg-gray-50 rounded">
                          <Skeleton width="40%" height="24px" />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                {screeningResponse && screeningResponse.company_details && screeningResponse.company_details.length === 0 ? (
                  <div className="mt-12 bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                    <h3 className="text-base font-bold text-yellow-900 mb-2">No Companies Passed Screening</h3>
                    <p className="text-sm text-yellow-800 mb-4">
                      The selected screening criteria resulted in zero companies. Please adjust your parameters or company selection and try again.
                    </p>
                    <button
                      onClick={resetScreening}
                      className="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
                    >
                      Try Screening Again
                    </button>
                  </div>
                ) : null}

                {screeningResponse?.company_details && screeningResponse.company_details.length > 0 ? (
                  <div className="mt-12" ref={screeningResultsRef}>
                    <h3 className="text-base font-bold text-black">List of companies passed the criteria</h3>
                    <p className="text-sm text-black mb-4">
                      {screeningResponse.company_details.length} companies passed screening criteria
                    </p>
                    <div className="space-y-1 max-h-[400px] overflow-y-auto">
                      {screeningResponse.company_details.map((row: any, index: number) => {
                        const companyName = row['Company '] || row['Company'] || row['company'] || 'Unknown Company';
                        const reason = row['Reason'] || row['reason'] || row['Screening Reason'] || row['screening_reason'] || '';
                        const isExpanded = !!expandedScreeningResults[index];
                        return (
                          <div key={index}>
                            <button
                              onClick={() => toggleScreeningResult(index)}
                              className="w-full flex items-center gap-2 py-2 px-1 text-left hover:bg-gray-50 transition-colors"
                            >
                              {isExpanded ? (
                                <FiChevronUp className="w-4 h-4 text-gray-600" />
                              ) : (
                                <FiChevronDown className="w-4 h-4 text-gray-600" />
                              )}
                              <span className="text-black font-bold text-md">{companyName}</span>
                            </button>
                            {isExpanded && reason && (
                              <div className="pl-8 pb-2 text-md">
                                <span className="text-gray-900 font-semibold">Reason:</span> <span className="text-black">{formatValue(reason)}</span>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
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
                <div className="pb-4">
                  <p className="text-sm text-black-800">
                    <strong>Step 3:</strong> Select required risk analysis parameters to identify potential risk of screened companies.
                  </p>
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

                    {isSubmitting && !riskAnalysisResponse ? (
                      <div ref={riskAnalysisResultsRef} className="mt-6">
                        <div className="mb-4">
                          <h3 className="text-lg font-bold text-gray-900">Risk Analysis Results</h3>
                          <p className="text-sm text-gray-600">Loading risk analysis...</p>
                        </div>
                        <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead className="sticky top-0 z-10">
                                <tr className="bg-[#BEBEBE]">
                                  <th className="px-2 py-3 text-left text-xs font-bold text-black w-12">S.No.</th>
                                  <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[150px]">Company Name</th>
                                  <th className="px-3 py-3 text-center text-xs font-bold text-black min-w-[120px]">Overall Status</th>
                                  <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[180px]">Category</th>
                                  <th className="px-3 py-3 text-center text-xs font-bold text-black min-w-[80px]">Status</th>
                                  <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[150px]">Reason</th>
                                </tr>
                              </thead>
                              <tbody>
                                {[1, 2, 3, 4, 5, 6].map((i) => (
                                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                                    <td className="px-2 py-3 text-sm text-black w-12"><Skeleton width="20px" height="20px" /></td>
                                    <td className="px-3 py-3 text-sm"><Skeleton width="100%" height="20px" /></td>
                                    <td className="px-3 py-3 text-sm text-center"><Skeleton width="60%" height="20px" /></td>
                                    <td className="px-3 py-3 text-sm"><Skeleton width="80%" height="20px" /></td>
                                    <td className="px-3 py-3 text-sm text-center"><Skeleton width="60%" height="20px" /></td>
                                    <td className="px-3 py-3 text-sm"><Skeleton width="90%" height="20px" /></td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {riskAnalysisResponse && riskAnalysisResponse.all_companies && riskAnalysisResponse.all_companies.length === 0 ? (
                      <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                        <h3 className="text-base font-bold text-yellow-900 mb-2">No Companies in Risk Analysis</h3>
                        <p className="text-sm text-yellow-800 mb-4">
                          The risk analysis returned no companies. Please adjust your risk parameters or select different companies from screening and try again.
                        </p>
                        <button
                          onClick={resetRiskAnalysis}
                          className="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
                        >
                          Try Again
                        </button>
                      </div>
                    ) : null}

                    {riskAnalysisResponse?.all_companies && riskAnalysisResponse.all_companies.length > 0 ? (
                      <div ref={riskAnalysisResultsRef} className="mt-6">
                        <div className="mb-4 flex items-center justify-between">
                          <div>
                            <h3 className="text-lg font-bold text-gray-900">Risk Analysis Results</h3>
                            <p className="text-sm text-gray-600">
                              {riskAnalysisResponse.summary?.passed ?? 0} out of {riskAnalysisResponse.summary?.total ?? 0} companies passed risk criteria
                            </p>
                          </div>
                          <button
                            onClick={exportRiskAnalysisToCSV}
                            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
                          >
                            Export as CSV
                          </button>
                        </div>
                        <div className="bg-white overflow-hidden rounded-lg shadow-[0_0_15px_rgba(0,0,0,0.15)]">
                          <div className="overflow-x-auto">
                            <table className="w-full">
                              <thead className="sticky top-0 z-10">
                                <tr className="bg-[#BEBEBE]">
                                  <th className="px-2 py-3 text-left text-xs font-bold text-black w-12">S.No.</th>
                                  <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[150px]">Company Name</th>
                                  <th className="px-3 py-3 text-center text-xs font-bold text-black min-w-[120px]">Overall Status</th>
                                  <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[180px]">Category</th>
                                  <th className="px-3 py-3 text-center text-xs font-bold text-black min-w-[80px]">Status</th>
                                  <th className="px-3 py-3 text-left text-xs font-bold text-black min-w-[300px]">Reason</th>
                                </tr>
                              </thead>
                              <tbody>
                                {riskAnalysisResponse.all_companies.map((company: any, companyIndex: number) => (
                                  company.risk_scores?.map((risk: any, riskIndex: number) => (
                                    <tr key={`${companyIndex}-${riskIndex}`} className="hover:bg-indigo-50 transition-colors border-b border-gray-200">
                                      {riskIndex === 0 && (
                                        <td rowSpan={company.risk_scores.length} className="px-2 py-3 text-sm text-black w-12 align-top font-semibold">
                                          {companyIndex + 1}.
                                        </td>
                                      )}
                                      {riskIndex === 0 && (
                                        <td rowSpan={company.risk_scores.length} className="px-3 py-3 text-sm text-indigo-600 font-bold align-top min-w-[150px] break-words">
                                          {company.company_name}
                                        </td>
                                      )}
                                      {riskIndex === 0 && (
                                        <td rowSpan={company.risk_scores.length} className="px-3 py-3 text-sm text-center font-bold align-top min-w-[120px]">
                                          <span className={`inline-block px-3 py-1 rounded text-xs font-semibold whitespace-nowrap ${
                                            String(company.overall_status).toUpperCase() === 'SAFE' ? 'bg-green-100 text-green-800' :
                                            String(company.overall_status).toUpperCase() === 'WARN' || String(company.overall_status).toUpperCase() === 'WARNING' ? 'bg-yellow-100 text-yellow-800' :
                                            String(company.overall_status).toUpperCase() === 'UNSAFE' || String(company.overall_status).toUpperCase() === 'RISK' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                                          }`}>
                                            {company.overall_status || '-'}
                                          </span>
                                        </td>
                                      )}
                                      <td className="px-3 py-3 text-sm text-gray-900 font-medium min-w-[180px]">{risk.category}</td>
                                      <td className="px-3 py-3 text-sm text-center min-w-[80px]">
                                        <span className={`inline-block px-2 py-1 rounded text-xs font-semibold whitespace-nowrap ${
                                          String(risk.status).toUpperCase() === 'SAFE' ? 'bg-green-100 text-green-800' :
                                          String(risk.status).toUpperCase() === 'WARN' || String(risk.status).toUpperCase() === 'WARNING' ? 'bg-yellow-100 text-yellow-800' :
                                          String(risk.status).toUpperCase() === 'UNSAFE' || String(risk.status).toUpperCase() === 'RISK' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                                        }`}>
                                          {risk.status}
                                        </span>
                                      </td>
                                      <td className="px-3 py-3 text-sm text-gray-700 min-w-[300px]" title={risk.reason}>
                                        <span className="block truncate">{risk.reason}</span>
                                      </td>
                                    </tr>
                                  ))
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                    <p className="text-sm text-blue-800">
                      <strong>Next Steps:</strong> No risk analysis parameters available. Risk analysis completed. You can now review the results or export this data.
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

      {/* Main Content Area with Streaming Panel */}
      <div className="flex-1 overflow-hidden">
        <div className="flex flex-row gap-6 px-6 py-6 h-full">
          {/* Main Content Container - Resizes based on Agent Thinking panel */}
          <div className={`flex-1 flex flex-col min-w-0 transition-all duration-300`}>
            {/* Left Panel - Wizard, Parameters, and Results */}
            <div className="flex-1 overflow-y-auto">
              <div className="w-full">
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

                    {currentStep === 2 && riskAnalysisList && riskAnalysisList.length > 0 && (
                      <button
                        onClick={handleAnalyzeRisk}
                        disabled={isSubmitting || riskAnalysisResponse ? true : getSelectedRiskAnalysisItems().length === 0}
                        className={`flex items-center space-x-2 px-6 py-3 rounded-lg font-medium transition-colors ${
                          isSubmitting || riskAnalysisResponse || getSelectedRiskAnalysisItems().length === 0
                            ? ' cursor-not-allowed'
                            : 'bg-indigo-600 text-white hover:bg-indigo-700'
                        }`}
                      >
                        {isSubmitting ? (
                          <span>Analyzing...</span>
                        ) : riskAnalysisResponse ? (
                          <span></span>
                        ) : (
                          <span>Analyze Risk</span>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Agent Thinking Container - Collapsible (Right Sidebar) */}
          {(showStreamingPanel || streamingEvents.length > 0) && (
            <div className={`transition-all duration-300 flex-shrink-0 ${agentThinkingOpen ? 'w-80' : 'w-12'}`}>
              <div className={`flex flex-col bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden sticky top-4 ${agentThinkingOpen ? 'h-[calc(100vh-240px)]' : ''}`}>
                {/* Header - Clickable to toggle */}
                <button
                  onClick={() => setAgentThinkingOpen(!agentThinkingOpen)}
                  className={`border-b border-gray-200 bg-white flex items-center flex-shrink-0 hover:bg-gray-50 transition-colors w-full ${agentThinkingOpen ? 'px-4 py-3 gap-3 text-left' : 'p-3 justify-center flex-col gap-1'}`}
                  title={agentThinkingOpen ? 'Collapse panel' : 'Expand Agent Thinking'}
                >
                  {agentThinkingOpen ? (
                    <>
                      <FiChevronRight className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                      <FiMessageSquare className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                      <span className="text-sm font-semibold text-gray-900">Agent Thinking</span>
                    </>
                  ) : (
                    <>
                      <FiMessageSquare className="w-5 h-5 text-indigo-600" />
                      <FiChevronLeft className="w-4 h-4 text-indigo-600" />
                    </>
                  )}
                </button>

                {/* Streaming Content */}
                {agentThinkingOpen && (
                  <div
                    ref={streamingPanelRef}
                    className="flex-1 overflow-y-auto p-4 bg-white"
                  >
                    {streamingEvents.length === 0 ? (
                      <div className="text-gray-400 text-sm">Waiting for agent output...</div>
                    ) : (
                      <div className="space-y-4">
                        {streamingEvents.map((event, idx) => {
                          const content = event.content || event.message || '';
                          const eventType = event.type || `Event ${idx + 1}`;
                          const cleanContent = typeof content === 'string'
                            ? content
                                .replace(/^[^\w\s]*\s*/g, '')
                                .replace(/^STEP\s*\d+:\s*/i, '')
                                .replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]|[\u{2700}-\u{27BF}]|[\u{1F600}-\u{1F64F}]|[\u{1F680}-\u{1F6FF}]/gu, '')
                                .trim()
                            : String(content);

                          if (!cleanContent) return null;

                          return (
                            <div
                              key={idx}
                              className="border-l-2 border-indigo-400 pl-4"
                            >
                              <div className="text-xs text-gray-500 mb-1 font-medium capitalize">{eventType}</div>
                              <p className="text-sm text-gray-800 leading-relaxed">{cleanContent}</p>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Loading Indicator */}
                {showStreamingPanel && agentThinkingOpen && (
                  <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 flex items-center gap-2 text-xs text-gray-600 flex-shrink-0">
                    <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                    Processing...
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Company Detail Dialog */}
      <Dialog
        open={companyDetailOpen}
        onClose={closeCompanyDetail}
        maxWidth="md"
        PaperProps={{ sx: { maxHeight: '85vh', width: '600px', borderRadius: '12px' } }}
      >
        <DialogTitle sx={{ 
          fontWeight: 'bold', 
          fontSize: '1.25rem', 
          padding: '20px', 
          background: '#FFFFFF',
          color: '#1F2937',
          borderBottom: '1px solid #E5E7EB',
          borderRadius: '12px 12px 0 0'
        }}>
          {selectedCompanyDetail?.['Company '] || selectedCompanyDetail?.['Company'] || 'Company Details'}
        </DialogTitle>
        <DialogContent sx={{ padding: '24px', overflowY: 'auto', maxHeight: 'calc(85vh - 130px)' }}>
          {selectedCompanyDetail && (
            <div className="space-y-6">
              {/* Company Attributes Grid */}
              <div className="grid grid-cols-3 gap-4">
                {Object.entries(selectedCompanyDetail).map(([key, value]: [string, any]) => {
                  // Skip Risks as we'll handle it separately
                  if (key === 'Risks' || key === 'risks' || key === 'Company ' || key === 'Company') {
                    return null;
                  }
                  return (
                    <div key={key} className="bg-gray-50 rounded-lg p-3 border border-gray-200 hover:border-gray-300 transition-colors">
                      <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1">{key}</div>
                      <div className="text-sm font-medium text-gray-900">{formatValue(value)}</div>
                    </div>
                  );
                })}
              </div>

              {/* Display Risks if available */}
              {(selectedCompanyDetail?.['Risks'] || selectedCompanyDetail?.['risks']) && (
                <div className="mt-2 pt-6 border-t border-gray-200">
                  <div className="text-lg font-bold text-gray-900 mb-4">Risk Assessment</div>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(selectedCompanyDetail['Risks'] || selectedCompanyDetail['risks']).map(([riskKey, riskValue]: [string, any]) => {
                      return (
                        <div key={riskKey} className="rounded-lg p-3 border border-gray-200 bg-gray-50">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="font-semibold text-sm text-gray-800">{riskKey}</div>
                              <div className="text-sm font-medium mt-1 text-gray-700">
                                {formatValue(riskValue)}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
        <DialogActions sx={{ padding: '16px 24px', borderTop: '1px solid #E5E7EB' }}>
          <Button
            onClick={closeCompanyDetail}
            variant="contained"
            size="small"
            sx={{ backgroundColor: '#4F46E5', '&:hover': { backgroundColor: '#4338CA' }, textTransform: 'none', borderRadius: '6px', fontWeight: '500' }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default SourcingAgent;