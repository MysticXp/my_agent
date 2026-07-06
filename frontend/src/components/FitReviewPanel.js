import React from 'react';
import FitAnalysis from './FitAnalysis';

const FitReviewPanel = ({ fitScores, fitAnalysis, onDecide, loading }) => {
  return (
    <div className="fit-review-panel" style={{
      background: 'white',
      padding: '20px',
      borderRadius: '16px',
      marginTop: '16px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
    }}>
      <div style={{
        background: '#e8f4fd',
        borderLeft: '4px solid #007bff',
        padding: '12px 16px',
        borderRadius: '8px',
        marginBottom: '16px',
      }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem' }}>📊 JD-简历契合度分析已完成</h3>
        <p style={{ margin: '8px 0 0', color: '#495057', fontSize: '0.95rem' }}>
          请查看下方的匹配分析结果，决定是否继续进行模拟面试。
        </p>
      </div>

      {/* Fit Analysis Score Card + Details */}
      <FitAnalysis scores={fitScores} analysis={fitAnalysis} />

      {/* Decision Buttons */}
      <div style={{
        display: 'flex',
        gap: '12px',
        justifyContent: 'center',
        marginTop: '20px',
        paddingTop: '16px',
        borderTop: '1px solid #eee',
      }}>
        <button
          onClick={() => onDecide('continue')}
          disabled={loading}
          style={{
            padding: '12px 32px',
            fontSize: '1rem',
            background: loading ? '#6c757d' : '#28a745',
          }}
        >
          {loading ? '处理中...' : '✅ 继续模拟面试'}
        </button>
        <button
          onClick={() => onDecide('skip')}
          disabled={loading}
          style={{
            padding: '12px 32px',
            fontSize: '1rem',
            background: loading ? '#6c757d' : '#6c757d',
          }}
        >
          {loading ? '处理中...' : '⏭️ 跳过，直接看报告'}
        </button>
      </div>
    </div>
  );
};

export default FitReviewPanel;
