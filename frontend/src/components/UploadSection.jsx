import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Loader2 } from 'lucide-react';
import './UploadSection.css';

const API_BASE = "http://10.224.213.198:8000";

const UploadSection = ({ onUploadComplete }) => {
  const [isDragActive, setIsDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [jobDescription, setJobDescription] = useState("We are looking for a Senior Frontend Engineer with expertise in React, CSS, and modern UI design.");
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only activate if files are actually being dragged
    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.includes('Files')) {
      setIsDragActive(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (file) => {
    setUploadError(null);

    // Client-side validation
    if (!file || file.size === 0) {
      setUploadError("Empty file detected. Please select a valid PDF.");
      return;
    }
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError("Only PDF files are accepted. Please upload a .pdf file.");
      return;
    }
    if (!jobDescription || jobDescription.trim().length < 10) {
      setUploadError("Please provide a more detailed Job Description (at least 10 characters).");
      return;
    }

    setIsUploading(true);

    const formData = new FormData();
    formData.append("resume", file);
    formData.append("job_description", jobDescription);

    try {
      const response = await fetch(`${API_BASE}/analyze-resume`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      console.log("analyze-resume response:", data);

      if (!response.ok) {
        throw new Error(data.detail || "Resume analysis failed");
      }

      setIsUploading(false);
      onUploadComplete(data);
    } catch (error) {
      console.error('Analysis error:', error);
      setIsUploading(false);
      setUploadError(`${error.message}`);
    }
  };

  return (
    <section className="upload-section" id="upload">
      <div className="upload-container">
        <h2 className="section-title">Initiate Analysis</h2>
        <p className="section-subtitle">Securely process resumes through our quantum-grade AI models</p>
        
        <div className="jd-input-wrapper fade-in-up">
            <label>Target Job Role & Description</label>
            <textarea 
              className="jd-textarea glass-panel"
              placeholder="Paste the job requirements here..."
              value={jobDescription}
              onChange={(e) => setJobDescription(e.target.value)}
            />
            <p className="jd-tip">Higher detail leads to more accurate AI alignment scores</p>
        </div>

        {uploadError && (
          <div className="upload-error glass-panel fade-in">
            <span>⚠️ {uploadError}</span>
          </div>
        )}

        <div 
          className={`drop-zone premium-glass ${isDragActive ? 'drag-active' : ''}`}
          onDragEnter={handleDragEnter}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
        >
          <div className="color-plate-glow"></div>
          <div className="neural-particles"></div>
          <div className="drop-content-wrapper">
          <input
            ref={fileInputRef}
            type="file"
            className="file-input hidden"
            onChange={handleChange}
            accept=".pdf"
          />
          
          {isUploading ? (
            <div className="upload-state uploading fade-in">
              <div className="scan-line"></div>
              <Loader2 className="spinner-icon" size={48} />
              <h3 className="text-gradient">Analyzing Neural Pathways...</h3>
              <p>Matching candidate skills against parameters</p>
            </div>
          ) : (
            <div className="upload-state idle">
              <div className="upload-icon-wrapper">
                <UploadCloud className="upload-icon" size={48} />
              </div>
              <h3>Drag & Drop Resume Here</h3>
              <p>or click to browse from local files (.pdf only)</p>
            </div>
          )}
          </div>
        </div>
      </div>
    </section>
  );
};

export default UploadSection;
