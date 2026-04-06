import React, { useEffect, useState } from 'react';
import { Target, Activity, ShieldAlert, AlertTriangle, CheckCircle, XCircle, Zap, BookOpen } from 'lucide-react';
import './Dashboard.css';

const ProgressBar = ({ label, targetValue, colorClass }) => {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => {
      setWidth(targetValue);
    }, 300);
    return () => clearTimeout(timer);
  }, [targetValue]);

  return (
    <div className="progress-container">
      <div className="progress-header">
        <span className="progress-label">{label}</span>
        <span className="progress-value">{width}%</span>
      </div>
      <div className="progress-track">
        <div 
          className={`progress-fill ${colorClass}`} 
          style={{ width: `${width}%` }} 
        />
      </div>
    </div>
  );
};

const TagList = ({ items, colorClass }) => (
  <div className="tag-list">
    {items.map((item, i) => (
      <span key={i} className={`tag ${colorClass}`}>{item}</span>
    ))}
  </div>
);

const Dashboard = ({ data }) => {
  if (!data) return null;

  const isFake = data.is_fake === true;
  const statusLabel = data.resume_status === "fake" 
    ? "Fake / Template-Based Resume Detected" 
    : data.resume_status === "real" 
      ? "Authentic Resume Verified" 
      : "Resume Status Unknown";

  const statusIcon = isFake 
    ? <XCircle size={22} /> 
    : <CheckCircle size={22} />;

  const statusClass = isFake ? "status-fake" : "status-real";

  return (
    <section className="dashboard-section" id="dashboard">
      <div className="dashboard-container">
        <h2 className="section-title">Analysis Complete</h2>

        {/* Status Banner */}
        <div className={`status-banner glass-panel ${statusClass}`}>
          {statusIcon}
          <span>{statusLabel}</span>
          {!data.ranked && <span className="ranked-badge">Not Ranked</span>}
          {data.ranked && <span className="ranked-badge ranked-yes">Ranked ✓</span>}
        </div>

        {/* Explanation */}
        {data.explanation && (
          <div className="explanation-panel glass-panel">
            <BookOpen size={18} />
            <p>{data.explanation}</p>
          </div>
        )}
        
        {/* Score Cards */}
        <div className="scores-grid">
          <div className="score-card glass-panel">
            <div className="score-icon green">
              <Target size={28} />
            </div>
            <div className="score-content">
              <h3>Match Score</h3>
              <p>Skills & Requirements Alignment</p>
              <div className="big-score gradient-green">{data.match_score ?? 0}%</div>
            </div>
          </div>

          <div className="score-card glass-panel">
            <div className="score-icon red">
              <ShieldAlert size={28} />
            </div>
            <div className="score-content">
              <h3>Fraud Score</h3>
              <p>Anomaly & Exaggeration Detection</p>
              <div className="big-score gradient-red">{data.fraud_score ?? 0}%</div>
            </div>
          </div>

          <div className="score-card glass-panel highlight-card">
            <div className="score-icon blue">
              <Activity size={28} />
            </div>
            <div className="score-content">
              <h3>Final Score</h3>
              <p>Overall Candidate Fit</p>
              <div className="big-score text-gradient">{data.final_score ?? 0}%</div>
            </div>
          </div>
        </div>

        {/* Score Bars */}
        <div className="detailed-metrics glass-panel">
          <h3 className="metrics-title">Score Breakdown</h3>
          <ProgressBar label="Match Score" targetValue={data.match_score ?? 0} colorClass="bg-green" />
          <ProgressBar label="Authenticity Score" targetValue={data.authenticity_score ?? 0} colorClass="bg-blue" />
          <ProgressBar label="Quality Score" targetValue={data.quality_score ?? 0} colorClass="bg-purple" />
          <ProgressBar label="Fraud Risk" targetValue={data.fraud_score ?? 0} colorClass="bg-red" />
        </div>

        {/* Skills Section (only for real resumes) */}
        {!isFake && data.skills && data.skills.length > 0 && (
          <div className="detail-section glass-panel">
            <h3 className="metrics-title"><Zap size={18} /> Matched Skills</h3>
            <TagList items={data.skills} colorClass="tag-green" />
          </div>
        )}

        {!isFake && data.missing_skills && data.missing_skills.length > 0 && (
          <div className="detail-section glass-panel">
            <h3 className="metrics-title"><AlertTriangle size={18} /> Missing Skills</h3>
            <TagList items={data.missing_skills} colorClass="tag-amber" />
          </div>
        )}

        {/* Fraud + Authenticity Reasons (for fake resumes) */}
        {isFake && data.fraud_reasons && data.fraud_reasons.length > 0 && (
          <div className="detail-section glass-panel section-danger">
            <h3 className="metrics-title"><ShieldAlert size={18} /> Fraud Indicators</h3>
            <ul className="reason-list">
              {data.fraud_reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        )}

        {isFake && data.authenticity_reasons && data.authenticity_reasons.length > 0 && (
          <div className="detail-section glass-panel section-danger">
            <h3 className="metrics-title"><XCircle size={18} /> Authenticity Flags</h3>
            <ul className="reason-list">
              {data.authenticity_reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </div>
        )}

        {/* Quality Warnings */}
        {data.quality_warnings && data.quality_warnings.length > 0 && (
          <div className="detail-section glass-panel">
            <h3 className="metrics-title"><AlertTriangle size={18} /> Quality Warnings</h3>
            <ul className="reason-list warning-list">
              {data.quality_warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        )}

      </div>
    </section>
  );
};

export default Dashboard;
