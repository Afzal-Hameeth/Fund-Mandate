import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../utils/constants';
import { FiUpload, FiFileText, FiSend, FiFile, FiTrash, FiChevronDown, FiChevronUp } from 'react-icons/fi';
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

  const extractedParamsRef = useRef<HTMLDivElement>(null);
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

    setIsSubmitting(true);
    setIsSubmitted(false);
    setParsedResult(null);
    setApiError(null);

    try {
      // Prepare multipart form data for the backend API
      const formData = new FormData();
      formData.append('pdf', selectedFile as File);
      formData.append('query', description.trim());

      const response = await fetch(`${API.BASE_URL()}/api/parse-mandate`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `API error: ${response.status}`);
      }

      const data = await response.json();
      
      // Debug: Log the actual response structure
      console.log('API Response:', data);
      console.log('Criteria structure:', data.criteria);

      // Store parsed result and show UI
      setParsedResult(data);
      setSelectedFile(null);
      setDescription('');
      setErrors({});
      
      // Show success toast
      toast.success('Fund mandate processed successfully! Parameters extracted.');
      
      setIsSubmitted(true);
    } catch (error) {
      console.error('Error submitting fund mandate:', error);
      const message = (error as any)?.message || 'Failed to submit fund mandate. Please try again.';
      setApiError(message);
      alert(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const getMandatoryThresholds = () => {
    // Check multiple possible paths for sourcing_parameters
    const thresholds = 
      parsedResult?.criteria?.mandate?.sourcing_parameters ??
      parsedResult?.criteria?.fund_mandate?.sourcing_parameters ??
      parsedResult?.criteria?.sourcing_parameters ??
      parsedResult?.sourcing_parameters ??
      null;
    
    if (!thresholds) {
      return [];
    }

    return Object.entries(thresholds).map(([key, value]) => ({
      key: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), // Convert snake_case to Title Case
      value: value as string
    }));
  };

  const getPreferredMetrics = () => {
    // Check multiple possible paths for screening_parameters
    const metrics = 
      parsedResult?.criteria?.mandate?.screening_parameters ??
      parsedResult?.criteria?.fund_mandate?.screening_parameters ??
      parsedResult?.criteria?.screening_parameters ??
      parsedResult?.screening_parameters ??
      null;
    
    if (!metrics) {
      return [];
    }

    return Object.entries(metrics).map(([key, value]) => ({
      key: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), // Convert snake_case to Title Case
      value: value as string
    }));
  };

  const getRiskFactors = () => {
    // Check multiple possible paths for risk_parameters and risk_analysis_parameters
    const factors = 
      parsedResult?.criteria?.mandate?.risk_parameters ??
      parsedResult?.criteria?.fund_mandate?.risk_parameters ??
      parsedResult?.criteria?.risk_parameters ??
      parsedResult?.criteria?.risk_parameters ??
      parsedResult?.risk_parameters ??
      parsedResult?.risk_parameters ??
      null;
    
    if (!factors) {
      return [];
    }

    return Object.entries(factors).map(([key, value]) => ({
      key: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()), // Convert snake_case to Title Case
      value: value as string
    }));
  };

  const canSubmit = !isSubmitting && selectedFile && description.trim() && !errors.file && !errors.description;

  return (
    <div className="flex flex-col min-h-full bg-gray-50">
      {/* Header */}
      <header className="border-b sticky top-0 bg-background/95 bg-white z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div>
                <h1 className="text-xl font-bold">Fund Mandate</h1>
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
        <div className="flex flex-col md:flex-row gap-8 px-8 py-8">
          {/* Left: Info Card */}
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
                Upload your fund mandate documents in PDF format. Provide a clear description to help our AI agent understand the context and requirements.
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
                  <div className="flex items-center">
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full mr-3 flex-shrink-0"></span>
                    <span>Clear description required</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Upload Form */}
          <div className="flex-1 max-w-2xl">
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
                  Description
                </label>
                <textarea
                  id="description"
                  value={description}
                  onChange={handleDescriptionChange}
                  placeholder="Provide a detailed description of this fund mandate, including objectives, requirements, and any specific instructions..."
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
        </div>

        {/* Post-Submission Section */}
        {isSubmitted && (
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

              {/* {parsedResult && (
                <div className="p-4 bg-white border border-gray-100 rounded-lg mb-6">
                  <h3 className="text-lg font-semibold mb-2">Raw API Response (Debug)</h3>
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 max-h-72 overflow-auto bg-gray-50 p-3 rounded">{JSON.stringify(parsedResult, null, 2)}</pre>
                </div>
              )} */}

              {/* Collapsible Sections (Fully naked/De-contained rows) */}
              <div className="space-y-2">
                {/* 1. Sourcing Agent Parameters */}
                <div className="transition-all duration-300">
                  <button
                    onClick={() => toggleSection('sourcing')}
                    className="w-full flex items-center gap-4 py-5 text-left border-b border-gray-100 hover:border-indigo-100 group transition-all"
                  >
                    {openSections.sourcing ? <FiChevronUp className="text-indigo-600 flex-shrink-0" /> : <FiChevronDown className="text-gray-300 group-hover:text-gray-400 flex-shrink-0" />}
                    <span className="font-bold text-gray-800 tracking-tight">Mandatory Thresholds (Sourcing)</span>
                  </button>
                  {openSections.sourcing && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
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
                    <span className="font-bold text-gray-800 tracking-tight">Preferred Metrics (Screening)</span>
                  </button>
                  {openSections.screening && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
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
                    <span className="font-bold text-gray-800 tracking-tight">Risk Factors (Risk Analysis)</span>
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
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FundMandate;