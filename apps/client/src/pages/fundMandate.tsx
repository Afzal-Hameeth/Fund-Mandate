import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../utils/constants';
import { FiUpload, FiSend, FiFile, FiTrash, FiChevronDown, FiChevronUp, FiChevronLeft, FiChevronRight, FiMessageSquare, FiX, FiChevronRight as FiArrowRight } from 'react-icons/fi';
import { Skeleton } from '@mui/material';
import toast from 'react-hot-toast';

const FundMandate: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [parsedResult, setParsedResult] = useState<any | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [errors, setErrors] = useState<{ file?: string; description?: string }>({});
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    sourcing: true,
    screening: false,
    risk: false,
  });

  // Streaming state
  const [streamingEvents, setStreamingEvents] = useState<any[]>([]);
  const [showStreamingPanel, setShowStreamingPanel] = useState(false);
  const [agentThinkingOpen, setAgentThinkingOpen] = useState(true);
  const [wsConnId, setWsConnId] = useState<string | null>(null);

  // Capabilities modal state
  const [showCapabilitiesModal, setShowCapabilitiesModal] = useState(false);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [capabilitiesResult, setCapabilitiesResult] = useState<any>(null);
  const [pendingSubmitData, setPendingSubmitData] = useState<{ file: File; description: string } | null>(null);
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set());

  const extractedParamsRef = useRef<HTMLDivElement>(null);
  const streamingPanelRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Auto-scroll to extracted parameters when submission is successful
  useEffect(() => {
    if (isSubmitted && extractedParamsRef.current) {
      extractedParamsRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      });
    }
  }, [isSubmitted]);

  // Auto-scroll streaming panel to bottom on new events
  useEffect(() => {
    if (streamingPanelRef.current) {
      streamingPanelRef.current.scrollTop = streamingPanelRef.current.scrollHeight;
    }
  }, [streamingEvents]);

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const validateFile = (file: File) => {
    const allowedTypes = ['application/pdf'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!allowedTypes.includes(file.type)) {
      return 'Only PDF files are allowed';
    }
    if (file.size > maxSize) {
      return 'File size must be less than 10MB';
    }
    return null;
  };

  const handleFileSelect = (file: File) => {
    const error = validateFile(file);
    if (error) {
      setErrors((prev) => ({ ...prev, file: error }));
      return;
    }

    setSelectedFile(file);
    setErrors((prev) => ({ ...prev, file: undefined }));
    setIsSubmitted(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
    e.target.value = ''; // Reset input
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDescription(e.target.value);
    setErrors((prev) => ({ ...prev, description: undefined }));
    setIsSubmitted(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    const newErrors: { file?: string; description?: string } = {};

    if (!selectedFile) {
      newErrors.file = 'Please select a PDF file';
    }

    if (!description.trim()) {
      newErrors.description = 'Please provide a description';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Step 1: Show analyzing spinner for 3 seconds
    setIsAnalyzing(true);
    setPendingSubmitData({ file: selectedFile as File, description: description.trim() });

    // Wait 3 seconds for the analyzing spinner
    await new Promise(resolve => setTimeout(resolve, 3000));
    setIsAnalyzing(false);

    // Step 2: Fetch capabilities with GET request
    setCapabilitiesLoading(true);
    setCapabilitiesResult(null);

    try {
      const capabilitiesUrl = API.makeResearchUrl(API.ENDPOINTS.CAPABILITIES.BASE_URL());
      console.log('Fetching capabilities from:', capabilitiesUrl);
      
      const response = await fetch(capabilitiesUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `API error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Capabilities result:', data);
      setCapabilitiesResult(data);
      setShowCapabilitiesModal(true);
    } catch (error) {
      console.error('Error fetching capabilities:', error);
      const message = (error as any)?.message || 'Failed to fetch capabilities. Proceeding with normal flow.';
      toast.error(message);
      // Continue with normal flow even if capabilities call fails
      proceedWithNormalFlow(selectedFile as File, description.trim());
    } finally {
      setCapabilitiesLoading(false);
    }
  };

  const proceedWithNormalFlow = async (file: File, query: string) => {
    setShowCapabilitiesModal(false);
    setIsSubmitting(true);
    setIsSubmitted(false);
    setParsedResult(null);
    setApiError(null);
    setStreamingEvents([]);
    setShowStreamingPanel(true);
    setAgentThinkingOpen(true);

    try {
      // Step 1: Upload file to /api/parse-mandate-upload
      const formData = new FormData();
      formData.append('file', file);
      formData.append('query', query);

      const uploadResponse = await fetch(API.makeUrl(API.ENDPOINTS.FUND_MANDATE.UPLOAD()), {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        const errorText = await uploadResponse.text();
        throw new Error(errorText || `Upload API error: ${uploadResponse.status}`);
      }

      const uploadData = await uploadResponse.json();
      console.log('Upload response:', uploadData);

      // Extract filename and query from upload response
      const filename = uploadData.filename || file.name;
      const queryData = uploadData.query || query;
      const connId = `mandate-${Date.now()}`;

      setWsConnId(connId);

      // Step 2: Connect to WebSocket for parsing with streaming
      const wsUrl = API.wsUrl(API.ENDPOINTS.FUND_MANDATE.WS_PARSE(connId));
      console.log('Connecting to WebSocket:', wsUrl);

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        // Send pdf_name and query to server (server expects pdf_name, not filename)
        ws.send(JSON.stringify({ pdf_name: filename, query: queryData }));
      };

      ws.onmessage = (event) => {
        try {
          const eventData = JSON.parse(event.data);
          console.log('WebSocket event:', eventData);

          setStreamingEvents((prev) => [...prev, eventData]);

          if (eventData.type === 'analysis_complete' && eventData.criteria) {
            // Extract and set parsed result from criteria
            const result = {
              criteria: eventData.criteria,
              message: eventData.message || '✅ Mandate parsing complete!'
            };
            setParsedResult(result);
            setShowStreamingPanel(false);
            setIsSubmitting(false);
            setIsSubmitted(true);
            setSelectedFile(null);
            setDescription('');
            setErrors({});

            toast.success('Mandate processed successfully! Parameters extracted.');
            ws.close();
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setApiError('WebSocket connection error');
        setShowStreamingPanel(false);
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
      };

    } catch (error) {
      console.error('Error submitting fund mandate:', error);
      const message = (error as any)?.message || 'Failed to submit fund mandate. Please try again.';
      setApiError(message);
      setShowStreamingPanel(false);
      setIsSubmitting(false);
      alert(message);
    }
  };

  const getMandatoryThresholds = () => {
    // Extract from new criteria structure: criteria.mandate.sourcing_parameters
    const thresholds = parsedResult?.criteria?.mandate?.sourcing_parameters ?? parsedResult?.criteria?.sourcing_parameters ??null;

    if (!thresholds) {
      return [];
    }

    return Object.entries(thresholds).map(([key, value]) => ({
      key: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      value: value as string
    }));
  };

  const getPreferredMetrics = () => {
    // Extract from new criteria structure: criteria.mandate.screening_parameters
    const metrics = parsedResult?.criteria?.mandate?.screening_parameters ?? parsedResult?.criteria?.screening_parameters ?? null;

    if (!metrics) {
      return [];
    }

    return Object.entries(metrics).map(([key, value]) => ({
      key: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      value: value as string
    }));
  };

  const getRiskFactors = () => {
    // Extract from new criteria structure: criteria.mandate.risk_parameters
    const factors = parsedResult?.criteria?.mandate?.risk_parameters ?? parsedResult?.criteria?.risk_parameters ?? null;

    if (!factors) {
      return [];
    }

    return Object.entries(factors).map(([key, value]) => ({
      key: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), // Convert snake_case to Title Case
      value: value as string
    }));
  };

  const toggleExpand = (key: string) => {
    const newExpanded = new Set(expandedItems);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedItems(newExpanded);
  };

  // Hierarchical tree component
  const HierarchicalTree = ({ data }: { data: any }) => {
    if (!Array.isArray(data) || data.length === 0) {
      return <div className="text-gray-500 text-sm">No capabilities found</div>;
    }

    return (
      <div className="space-y-1">
        {data.map((capability: any) => (
          <div key={capability.id}>
            {/* Capability Level */}
            <button
              onClick={() => toggleExpand(`cap-${capability.id}`)}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors text-left group"
            >
              <div className="flex-shrink-0 w-5">
                {expandedItems.has(`cap-${capability.id}`) ? (
                  <FiChevronDown className="w-4 h-4 text-indigo-600" />
                ) : (
                  <FiArrowRight className="w-4 h-4 text-gray-400" />
                )}
              </div>
              <span className="font-semibold text-gray-900 text-sm">{capability.name}</span>
              {capability.vertical && (
                <span className="text-xs text-gray-500 ml-auto">{capability.vertical}</span>
              )}
            </button>

            {/* Processes */}
            {expandedItems.has(`cap-${capability.id}`) && capability.processes && (
              <div className="ml-4 border-l border-gray-200 pl-2">
                {capability.processes.map((process: any) => (
                  <div key={process.id}>
                    <button
                      onClick={() => toggleExpand(`proc-${process.id}`)}
                      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors text-left group"
                    >
                      <div className="flex-shrink-0 w-5">
                        {expandedItems.has(`proc-${process.id}`) ? (
                          <FiChevronDown className="w-4 h-4 text-indigo-600" />
                        ) : (
                          <FiArrowRight className="w-4 h-4 text-gray-400" />
                        )}
                      </div>
                      <span className="font-medium text-gray-800 text-sm">{process.name}</span>
                      {process.level && (
                        <span className="text-xs text-gray-500 ml-auto bg-gray-100 px-2 py-0.5 rounded">{process.level}</span>
                      )}
                    </button>

                    {/* Subprocesses */}
                    {expandedItems.has(`proc-${process.id}`) && process.subprocesses && (
                      <div className="ml-4 border-l border-gray-200 pl-2">
                        {process.subprocesses.map((subprocess: any) => (
                          <div key={subprocess.id}>
                            <button
                              onClick={() => toggleExpand(`subproc-${subprocess.id}`)}
                              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors text-left group"
                            >
                              <div className="flex-shrink-0 w-5">
                                {subprocess.data_entities && subprocess.data_entities.length > 0 ? (
                                  expandedItems.has(`subproc-${subprocess.id}`) ? (
                                    <FiChevronDown className="w-4 h-4 text-indigo-600" />
                                  ) : (
                                    <FiArrowRight className="w-4 h-4 text-gray-400" />
                                  )
                                ) : (
                                  <div className="w-4" />
                                )}
                              </div>
                              <span className="text-gray-700 text-sm">{subprocess.name}</span>
                              {subprocess.category && (
                                <span className="text-xs text-gray-500 ml-auto bg-gray-100 px-2 py-0.5 rounded">{subprocess.category}</span>
                              )}
                            </button>

                            {/* Data Entities */}
                            {expandedItems.has(`subproc-${subprocess.id}`) && subprocess.data_entities && (
                              <div className="ml-4 border-l border-gray-200 pl-2">
                                {subprocess.data_entities.map((dataEntity: any) => (
                                  <div key={dataEntity.data_entity_id}>
                                    <button
                                      onClick={() => toggleExpand(`entity-${dataEntity.data_entity_id}`)}
                                      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 rounded-lg transition-colors text-left group"
                                    >
                                      <div className="flex-shrink-0 w-5">
                                        {dataEntity.data_elements && dataEntity.data_elements.length > 0 ? (
                                          expandedItems.has(`entity-${dataEntity.data_entity_id}`) ? (
                                            <FiChevronDown className="w-4 h-4 text-indigo-600" />
                                          ) : (
                                            <FiArrowRight className="w-4 h-4 text-gray-400" />
                                          )
                                        ) : (
                                          <div className="w-4" />
                                        )}
                                      </div>
                                      <span className="text-gray-700 text-sm">{dataEntity.data_entity_name}</span>
                                      {dataEntity.data_elements && (
                                        <span className="text-xs text-gray-500 ml-auto bg-gray-100 px-2 py-0.5 rounded">
                                          {dataEntity.data_elements.length} items
                                        </span>
                                      )}
                                    </button>

                                    {/* Data Elements */}
                                    {expandedItems.has(`entity-${dataEntity.data_entity_id}`) && dataEntity.data_elements && (
                                      <div className="ml-4 border-l border-gray-200 pl-2">
                                        {dataEntity.data_elements.map((dataElement: any) => (
                                          <div
                                            key={dataElement.data_element_id}
                                            className="flex items-center gap-2 px-3 py-2 text-left group hover:bg-gray-100 rounded-lg transition-colors"
                                          >
                                            <div className="flex-shrink-0 w-5 flex items-center justify-center">
                                              <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full" />
                                            </div>
                                            <span className="text-gray-600 text-sm">{dataElement.data_element_name}</span>
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  const canSubmit = !isSubmitting && selectedFile && description.trim() && !errors.file && !errors.description;

  // Analyzing Overlay Component
  const AnalyzingOverlay = () => (
    <>
      {isAnalyzing && (
        <div className="fixed inset-0 flex items-center justify-center z-[999]">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" />
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md z-[999] overflow-hidden flex flex-col items-center justify-center p-8">
            <div className="animate-spin mb-6">
              <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full" />
            </div>
            <p className="text-gray-700 font-medium text-center">User intent is getting analyzed by Capability Compass</p>
          </div>
        </div>
      )}
    </>
  );

  // Capabilities Modal
  const CapabilitiesModal = () => (
    <>
      {/* Capabilities Modal */}
      {showCapabilitiesModal && (
        <div className="fixed inset-0 flex items-center justify-center z-[999]">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => !capabilitiesLoading && setShowCapabilitiesModal(false)} />
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl z-[999] h-[50vh] overflow-hidden flex flex-col max-h-[80vh]">
            {/* Modal Header */}
            <div className="border-b border-gray-100 px-6 py-3 bg-gray-50 flex items-center gap-3">
              <h2 className="text-lg font-bold text-gray-900">Capabilities Analysis Results</h2>
            </div>

            {/* Modal Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {capabilitiesLoading ? (
                <div className="flex flex-col items-center justify-center h-40">
                  <div className="animate-spin mb-4">
                    <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full" />
                  </div>
                  <p className="text-gray-600 text-sm">Fetching capabilities...</p>
                </div>
              ) : capabilitiesResult ? (
                <div>
                  {Array.isArray(capabilitiesResult) ? (
                    <HierarchicalTree data={capabilitiesResult} />
                  ) : typeof capabilitiesResult === 'object' ? (
                    <HierarchicalTree data={[capabilitiesResult]} />
                  ) : (
                    <div className="text-gray-500 text-sm">Unable to parse capabilities data</div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-32 text-gray-500">
                  <p>No results to display</p>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="border-t border-gray-100 px-6 py-3 bg-gray-50 flex items-center gap-3 flex-shrink-0">
              <button
                onClick={() => setShowCapabilitiesModal(false)}
                disabled={capabilitiesLoading}
                className="flex-1 px-3 py-1.5 rounded-md text-gray-600 hover:bg-gray-100 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (pendingSubmitData) {
                    proceedWithNormalFlow(pendingSubmitData.file, pendingSubmitData.description);
                  }
                }}
                disabled={capabilitiesLoading}
                className="flex-1 px-4 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  return (
    <div className="flex flex-col min-h-full bg-gray-50">
      {/* Analyzing Overlay */}
      <AnalyzingOverlay />
      {/* Capabilities Modal */}
      <CapabilitiesModal />
      {/* Header */}
      <header className="border-b sticky top-0 bg-background/95 bg-white z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div>
                <h1 className="text-xl font-bold">Mandate Processing</h1>
                <p className="text-xs text-muted-foreground">
                  Upload and process fund mandate documents
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="flex flex-col gap-8 px-8 py-8">
          {/* Form Section */}
          <div className={`flex ${isSubmitting ? 'flex-row' : 'flex-col md:flex-row'} gap-8`}>
            {/* Left: Info Card (hide after upload) */}
            {!isSubmitting && !isSubmitted && (
              <div className="flex flex-col gap-3 md:w-1/3">
                <div className="p-4 border border-indigo-200 rounded-xl bg-gradient-to-br from-indigo-50 via-white to-indigo-50/50 shadow-sm hover:shadow-md transition-all duration-300">
                  <div className="flex items-start mb-3">
                    <div className="p-2 bg-indigo-100 rounded-xl mr-3 shadow-sm">
                      <FiFile className="w-5 h-5 text-indigo-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-gray-900 mb-1">Fund Mandate PDF</h3>
                      <p className="text-sm text-indigo-600 font-medium">Document Upload</p>
                    </div>
                  </div>

                  <p className="text-gray-600 text-sm leading-relaxed mb-3">
                    Upload your fund mandate documents in PDF format. Fund mandate document contains set of rules and guidelines that defines how a fund must be managed.
                  </p>

                  <div className="bg-white/70 rounded-lg p-3 border border-indigo-100 mb-3">
                    <div className="flex items-center mb-2">

                      <p className="text-sm font-semibold text-gray-800">Requirements</p>
                    </div>
                    <div className="space-y-1 text-sm text-gray-600">
                      <div className="flex items-center">
                        <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full mr-3 flex-shrink-0"></span>
                        <span>PDF files only</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Right: Upload Form + Streaming Panel (full width after upload) */}
            <div className={`flex gap-8 ${isSubmitting ? 'w-full' : 'flex-1'}`}>
              {/* Form */}
              <div className={`flex-1 ${isSubmitting ? 'max-w-full' : 'max-w-2xl'}`}>
                <form onSubmit={handleSubmit} className="space-y-4">
              {/* PDF Upload Section */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Upload Fund Mandate PDF
                </label>

                <div className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
                  selectedFile
                    ? 'border-indigo-400 bg-indigo-50'
                    : 'border-indigo-300 hover:border-indigo-400 hover:bg-indigo-50'
                }`}>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileInput}
                    className="hidden"
                    id="fund-mandate-upload"
                    disabled={isSubmitting}
                  />
                  <label
                    htmlFor="fund-mandate-upload"
                    className={`cursor-pointer ${isSubmitting ? 'cursor-not-allowed opacity-50' : ''}`}
                  >
                    <FiUpload className={`w-12 h-12 mx-auto mb-4 ${selectedFile ? 'text-indigo-500' : 'text-indigo-400'}`} />
                    <p className="text-sm font-medium text-gray-900 mb-1">
                      Click to upload PDF file
                    </p>
                    <p className="text-xs text-gray-500">
                      PDF files only, up to 10MB
                    </p>
                  </label>
                </div>

                {errors.file && (
                  <div className="p-2 bg-red-50 border border-red-200 rounded-lg mt-2">
                    <p className="text-red-600 text-sm">{errors.file}</p>
                  </div>
                )}

                {selectedFile && !errors.file && (
                  <div className="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="text-indigo-700 text-sm">{selectedFile.name}</span>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedFile(null);
                          setErrors((prev) => ({ ...prev, file: undefined }));
                        }}
                        disabled={isSubmitting}
                        className="text-red-500 hover:text-red-700"
                      >
                        <FiTrash className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Description Section */}
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                  User Intent
                </label>
                <textarea
                  id="description"
                  value={description}
                  onChange={handleDescriptionChange}
                  placeholder="Provide a detailed user intent of this fund mandate, including objectives, requirements, and any specific instructions..."
                  className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 min-h-[80px] text-sm"
                  disabled={isSubmitting}
                  required
                />

                {errors.description && (
                  <div className="p-2 bg-red-50 border border-red-200 rounded-lg mt-2">
                    <p className="text-red-600 text-sm">{errors.description}</p>
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <div className="flex justify-end pt-3">
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className={`px-6 py-2 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 ${canSubmit
                    ? 'bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-lg focus:bg-indigo-700 active:scale-95'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <FiSend size={18} />
                      Submit
                    </>
                  )}
                </button>
              </div>
            </form>
              </div>

              {/* Agent Thinking Container - Collapsible (Right Sidebar) */}
              {(showStreamingPanel || streamingEvents.length > 0) && (
                <div className={`transition-all duration-300 flex-shrink-0 ${agentThinkingOpen ? 'w-72' : 'w-10'}`}>
                  <div className="flex flex-col bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden h-[calc(100vh-280px)] sticky top-4">
                    {/* Header - Clickable to toggle with chevron */}
                    <button
                      onClick={() => setAgentThinkingOpen(!agentThinkingOpen)}
                      className="px-3 py-3 border-b border-gray-200 bg-white flex items-center gap-2 flex-shrink-0 hover:bg-gray-50 transition-colors w-full text-left"
                    >
                      {agentThinkingOpen ? (
                        <FiChevronRight className="w-4 h-4 text-gray-600 flex-shrink-0" />
                      ) : (
                        <FiChevronLeft className="w-4 h-4 text-gray-600 flex-shrink-0" />
                      )}
                      {agentThinkingOpen && (
                        <>
                          <FiMessageSquare className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                          <span className="text-sm font-semibold text-gray-900">Agent Thinking</span>
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
        </div>

        {/* Post-Submission Section */}
        {(isSubmitting || isSubmitted) && (
          <div ref={extractedParamsRef} className="px-8 pb-16 animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="max-w-4xl mx-auto space-y-10">
              {/* Introduction Header Area (De-contained) */}
              <div>
                  <h2 className="text-lg font-bold text-gray-900 mb-2 tracking-tight">Extracted Parameters</h2>
                <p className="text-sm text-gray-500 leading-relaxed font-medium">
                  List of Agent Parameters extracted from Parsed PDF Document for Sourcing, Screening and Risk Analysis.
                </p>
              </div>

              {apiError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-red-700 text-sm">{apiError}</p>
                </div>
              )}

              {/* Loading Skeleton */}
              {isSubmitting && !isSubmitted && (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="space-y-4">
                      <Skeleton variant="text" width="30%" height={40} />
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {[1, 2, 3].map((j) => (
                          <Skeleton key={j} variant="rectangular" height={80} sx={{ borderRadius: 1 }} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* {parsedResult && (
                <div className="p-4 bg-white border border-gray-100 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold mb-2">Raw API Response (Debug)</h3>
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 max-h-72 overflow-auto bg-gray-50 p-3 rounded">{JSON.stringify(parsedResult, null, 2)}</pre>
                </div>
              )} */}

              {/* Collapsible Sections (Fully naked/De-contained rows) */}
              {isSubmitted && (
                <div className="space-y-2">
                {/* 1. Sourcing Agent Parameters */}
                <div className="transition-all duration-300">
                  <button
                    onClick={() => toggleSection('sourcing')}
                    className="w-full flex items-center gap-4 py-5 text-left border-b border-gray-100 hover:border-indigo-100 group transition-all"
                  >
                    {openSections.sourcing ? <FiChevronUp className="text-indigo-600 flex-shrink-0" /> : <FiChevronDown className="text-gray-300 group-hover:text-gray-400 flex-shrink-0" />}
                    <span className="font-bold text-gray-800 tracking-tight">Sector & Industry Research</span>
                  </button>
                  {openSections.sourcing && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {getMandatoryThresholds().map((threshold) => (
                          <div key={threshold.key} className="flex flex-col gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0" />
                              <span className="text-sm font-semibold text-gray-800">{threshold.key}</span>
                            </div>
                            <span className="text-sm text-gray-600 ml-4">{threshold.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* 2. Screening Agent Parameters */}
                <div className="transition-all duration-300">
                  <button
                    onClick={() => toggleSection('screening')}
                    className="w-full flex items-center gap-4 py-5 text-left border-b border-gray-100 hover:border-indigo-100 group transition-all"
                  >
                    {openSections.screening ? <FiChevronUp className="text-indigo-600 flex-shrink-0" /> : <FiChevronDown className="text-gray-300 group-hover:text-gray-400 flex-shrink-0" />}
                    <span className="font-bold text-gray-800 tracking-tight">Bottom-Up Fundamental Analysis</span>
                  </button>
                  {openSections.screening && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                        {getPreferredMetrics().map((metric) => (
                          <div key={metric.key} className="flex flex-col gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0" />
                              <span className="text-sm font-semibold text-gray-800">{metric.key}</span>
                            </div>
                            <span className="text-sm text-gray-600 ml-4">{metric.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* 3. Risk Factors Parameters */}
                <div className="transition-all duration-300">
                  <button
                    onClick={() => toggleSection('risk')}
                    className="w-full flex items-center gap-4 py-5 text-left border-b border-gray-100 hover:border-indigo-100 group transition-all"
                  >
                    {openSections.risk ? <FiChevronUp className="text-indigo-600 flex-shrink-0" /> : <FiChevronDown className="text-gray-300 group-hover:text-gray-400 flex-shrink-0" />}
                    <span className="font-bold text-gray-800 tracking-tight">Risk Assessment of Investment Ideas</span>
                  </button>
                  {openSections.risk && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
                        {getRiskFactors().map((factor) => (
                          <div key={factor.key} className="flex flex-col gap-2 p-3 bg-gray-50 rounded-lg border border-gray-200">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0" />
                              <span className="text-sm font-semibold text-gray-800">{factor.key}</span>
                            </div>
                            <span className="text-sm text-gray-600 ml-4">{factor.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex justify-end pt-4">
                  <button
                    type="button"
                    onClick={() => navigate('/sourcing-agent', { state: { sourcing: getMandatoryThresholds(), parsedResult } })}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700"
                  >
                    Continue
                  </button>
                </div>
              </div>
            )}
          </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FundMandate;