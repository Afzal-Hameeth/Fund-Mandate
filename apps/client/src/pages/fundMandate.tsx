import React, { useState } from 'react';
import { FiUpload, FiFileText, FiSend, FiFile, FiTrash, FiChevronDown, FiChevronUp } from 'react-icons/fi';

const FundMandate: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [errors, setErrors] = useState<{ file?: string; description?: string }>({});
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    sourcing: true,
    screening: false,
    risk: false,
  });

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

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFileSelect(files[0]);
    }
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

    try {
      // TODO: Implement file upload to backend
      console.log('Submitting:', {
        file: selectedFile!.name,
        description: description.trim(),
      });

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));

      alert('Fund mandate submitted successfully!');
      setSelectedFile(null);
      setDescription('');
      setErrors({});
      setIsSubmitted(true);
    } catch (error) {
      console.error('Error submitting fund mandate:', error);
      alert('Failed to submit fund mandate. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = !isSubmitting && selectedFile && description.trim() && !errors.file && !errors.description;

  return (
    <div className="flex flex-col min-h-full bg-gray-50">
      {/* Header */}
      <header className="border-b sticky top-0 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 z-50">
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

                <div
                  className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all duration-200 ${dragActive
                    ? 'border-indigo-400 bg-indigo-50 scale-[1.02]'
                    : selectedFile
                      ? 'border-indigo-400 bg-indigo-50'
                      : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50'
                    }`}
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                >
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileInput}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    disabled={isSubmitting}
                    id="fund-mandate-upload"
                  />

                  <label
                    htmlFor="fund-mandate-upload"
                    className={`cursor-pointer ${isSubmitting ? 'cursor-not-allowed opacity-50' : ''}`}
                  >
                    <div className="flex flex-col items-center">
                      {selectedFile ? (
                        <>
                          <FiFileText size={40} className="text-indigo-500 mb-3" />
                          <p className="text-sm font-medium text-gray-900 mb-1">
                            {selectedFile.name}
                          </p>
                          <p className="text-xs text-gray-500 mb-2">
                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                          </p>

                        </>
                      ) : (
                        <>
                          <FiUpload size={32} className="text-gray-400 mb-3" />
                          <p className="text-sm font-medium text-gray-900 mb-1">
                            Drop your PDF here, or click to browse
                          </p>
                          <p className="text-xs text-gray-500">
                            PDF files only, up to 10MB
                          </p>
                        </>
                      )}
                    </div>
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
                      <div className="flex items-center">
                        <FiFileText className="w-4 h-4 text-indigo-600 mr-2" />
                        <span className="text-indigo-700 text-sm font-medium">
                          {selectedFile.name} uploaded
                        </span>
                      </div>
                      <div className="flex items-center ml-4">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            e.preventDefault();
                            setSelectedFile(null);
                            setErrors((prev) => ({ ...prev, file: undefined }));
                          }}
                          aria-label="Remove file"
                          className="text-red-600 hover:text-red-800 transition-colors p-1 rounded"
                          disabled={isSubmitting}
                        >
                          <FiTrash className="w-4 h-4" />
                        </button>
                      </div>
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
          <div className="px-8 pb-16 animate-in fade-in slide-in-from-top-4 duration-500">
            <div className="max-w-4xl mx-auto space-y-10">
              {/* Introduction Header Area (De-contained) */}
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">Fund Mandate</h2>
                <p className="text-gray-500 leading-relaxed font-medium">
                  Define your fund parameters to guide the target screening process,
                  Expand sections below to customize each agent's configuration.
                </p>
              </div>

              {/* Collapsible Sections (Fully naked/De-contained rows) */}
              <div className="space-y-2">
                {/* 1. Sourcing Agent Parameters */}
                <div className="transition-all duration-300">
                  <button
                    onClick={() => toggleSection('sourcing')}
                    className="w-full flex items-center gap-4 py-5 text-left border-b border-gray-100 hover:border-indigo-100 group transition-all"
                  >
                    {openSections.sourcing ? <FiChevronUp className="text-indigo-600 flex-shrink-0" /> : <FiChevronDown className="text-gray-300 group-hover:text-gray-400 flex-shrink-0" />}
                    <span className="font-bold text-gray-800 tracking-tight">Sourcing Agent Parameters</span>
                  </button>
                  {openSections.sourcing && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {['Country', 'Sector', 'Industry'].map((param) => (
                          <div key={param} className="flex items-center gap-3.5 text-sm font-medium text-gray-600">
                            <span className="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0" />
                            {param}
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
                    <span className="font-bold text-gray-800 tracking-tight">Screening Agent Parameters</span>
                  </button>
                  {openSections.screening && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                          "Ebitda", "Growth", "Gross profit margin", "Net income",
                          "Return on equity", "Debt to equity", "Pe ratio",
                          "Price to book", "Market cap", "Dividend yield"
                        ].map((param) => (
                          <div key={param} className="flex items-center gap-3.5 text-sm font-medium text-gray-600">
                            <span className="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0" />
                            {param}
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
                    <span className="font-bold text-gray-800 tracking-tight">Risk Factors Parameters</span>
                  </button>
                  {openSections.risk && (
                    <div className="py-6 animate-in fade-in slide-in-from-top-1 duration-300">
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {[
                          "Competitive Position", "Governance Quality", "Customer Concentration Risk",
                          "Vendor / Platform Dependency", "Regulatory / Legal Risk", "Business Model Complexity"
                        ].map((param) => (
                          <div key={param} className="flex items-center gap-3.5 text-sm font-medium text-gray-600">
                            <span className="w-2 h-2 bg-indigo-400 rounded-full flex-shrink-0" />
                            {param}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
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