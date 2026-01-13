import React, { useState } from 'react';
import { FiUpload, FiFileText, FiSend } from 'react-icons/fi';

const FundMandate: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const handleFileSelect = (file: File) => {
    if (file.type === 'application/pdf') {
      setSelectedFile(file);
    } else {
      alert('Please select a PDF file only.');
    }
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !description.trim()) {
      alert('Please select a PDF file and provide a description.');
      return;
    }

    setIsSubmitting(true);

    try {
      // TODO: Implement file upload to backend
      console.log('Submitting:', {
        file: selectedFile.name,
        description: description.trim(),
      });

      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));

      alert('Fund mandate submitted successfully!');
      setSelectedFile(null);
      setDescription('');
    } catch (error) {
      console.error('Error submitting fund mandate:', error);
      alert('Failed to submit fund mandate. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-xl font-bold">Fund Mandate</h1>
        <p className="text-xs text-muted-foreground">Upload and process fund mandate documents</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* PDF Upload Section */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Upload Fund Mandate PDF
                </label>

                <div
                  className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    dragActive
                      ? 'border-indigo-400 bg-indigo-50'
                      : selectedFile
                      ? 'border-green-400 bg-green-50'
                      : 'border-gray-300 hover:border-gray-400'
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
                  />

                  <div className="flex flex-col items-center">
                    {selectedFile ? (
                      <>
                        <FiFileText size={48} className="text-green-500 mb-4" />
                        <p className="text-sm font-medium text-gray-900 mb-1">
                          {selectedFile.name}
                        </p>
                        <p className="text-xs text-gray-500">
                          {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                        <button
                          type="button"
                          onClick={() => setSelectedFile(null)}
                          className="mt-3 text-sm text-red-600 hover:text-red-800"
                          disabled={isSubmitting}
                        >
                          Remove file
                        </button>
                      </>
                    ) : (
                      <>
                        <FiUpload size={48} className="text-gray-400 mb-4" />
                        <p className="text-sm font-medium text-gray-900 mb-1">
                          Drop your PDF here, or click to browse
                        </p>
                        <p className="text-xs text-gray-500">
                          PDF files only, up to 10MB
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Description Section */}
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-3">
                  Description
                </label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Provide a description for this fund mandate..."
                  className="w-full resize-none rounded-lg border border-gray-300 px-4 py-3 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 min-h-[120px]"
                  disabled={isSubmitting}
                  required
                />
                <p className="text-xs text-gray-500 mt-2">
                  Describe the fund mandate requirements, objectives, or any specific instructions.
                </p>
              </div>

              {/* Submit Button */}
              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={!selectedFile || !description.trim() || isSubmitting}
                  className={`px-6 py-2.5 rounded-lg font-medium transition-all duration-200 flex items-center gap-2 ${
                    selectedFile && description.trim() && !isSubmitting
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700 hover:shadow-md focus:bg-indigo-700 active:scale-95'
                      : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <FiSend size={16} />
                      Submit Fund Mandate
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FundMandate;