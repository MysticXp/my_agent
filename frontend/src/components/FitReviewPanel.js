import React from 'react';
import FitAnalysis from './FitAnalysis';

const FitReviewPanel = ({ fitScores, fitAnalysis, similarJds, similarQuestions, onDecide, loading }) => {
  // 构建历史 JD 列表
  const historyJds = similarJds && similarJds.length > 0 ? similarJds : [];

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

      {/* Similar Historical JDs (RAG) */}
      {historyJds.length > 0 && (
        <div style={{
          marginTop: '16px',
          padding: '16px',
          background: '#f8f9fa',
          borderRadius: '12px',
        }}>
          <h4 style={{ margin: '0 0 12px', fontSize: '0.95rem', color: '#495057' }}>
            🔗 历史相似JD参考（RAG检索 — 供Agent参考用）
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {historyJds.map((jd, idx) => (
              <div key={jd.id || idx} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '10px 12px',
                background: 'white',
                borderRadius: '8px',
                border: '1px solid #e9ecef',
                fontSize: '0.85rem',
              }}>
                <span style={{
                  flexShrink: 0,
                  width: '24px',
                  height: '24px',
                  background: '#e8f4fd',
                  color: '#007bff',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 'bold',
                }}>
                  {idx + 1}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>
                    {jd.company || '?'} — {jd.role || '?'}
                    {jd.level && <span style={{ color: '#6c757d', fontWeight: 400 }}> · {jd.level}</span>}
                  </div>
                  <div style={{ color: '#6c757d', fontSize: '0.8rem', marginTop: '2px' }}>
                    {jd.similarity_reason}
                    {jd.fit_score > 0 && (
                      <span style={{
                        marginLeft: '8px',
                        color: jd.fit_score >= 75 ? '#28a745' : jd.fit_score >= 60 ? '#856404' : '#dc3545',
                        fontWeight: 600,
                      }}>
                        契合度{jd.fit_score}分
                      </span>
                    )}
                    <span style={{ marginLeft: '8px', color: '#adb5bd' }}>{jd.created_at}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historical Questions (from JSON store, by role) */}
      {similarQuestions && similarQuestions.length > 0 && (
        <div style={{
          marginTop: '16px',
          padding: '16px',
          background: '#f0f4ff',
          borderRadius: '12px',
        }}>
          <h4 style={{ margin: '0 0 12px', fontSize: '0.95rem', color: '#495057' }}>
            🎯 历史面试题（同岗位，共 {similarQuestions.length} 道）
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {similarQuestions.slice(0, 10).map((q, idx) => (
              <div key={idx} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                padding: '10px 12px',
                background: 'white',
                borderRadius: '8px',
                border: '1px solid #cfe2ff',
                fontSize: '0.85rem',
              }}>
                <span style={{
                  flexShrink: 0,
                  width: '24px',
                  height: '24px',
                  background: '#6610f2',
                  color: 'white',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 'bold',
                }}>
                  {idx + 1}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500 }}>
                    {q.question}
                  </div>
                  <div style={{ color: '#6c757d', fontSize: '0.75rem', marginTop: '4px' }}>
                    {q.company && <span style={{ marginRight: '8px' }}>🏢 {q.company}</span>}
                    {q.created_at && <span>{q.created_at}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
