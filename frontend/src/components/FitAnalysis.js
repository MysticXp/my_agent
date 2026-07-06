import React from 'react';

const GRADE_COLORS = {
  'S': { bg: '#d4edda', text: '#155724', border: '#28a745' },
  'A': { bg: '#d1ecf1', text: '#0c5460', border: '#17a2b8' },
  'B': { bg: '#fff3cd', text: '#856404', border: '#ffc107' },
  'C': { bg: '#ffe5cc', text: '#cc6600', border: '#fd7e14' },
  'D': { bg: '#f8d7da', text: '#721c24', border: '#dc3545' },
};

const GRADE_LABELS = {
  'S': '高度匹配',
  'A': '良好匹配',
  'B': '基本匹配',
  'C': '匹配偏低',
  'D': '不匹配',
};

const DIMENSION_LABELS = {
  skill_score: '核心技能',
  experience_score: '经验年限',
  education_score: '学历资质',
  responsibility_score: '职责覆盖',
  soft_skill_score: '软技能',
  bonus_score: '加分项',
};

const FitAnalysis = ({ scores, analysis }) => {
  if (!scores && !analysis) return null;

  const grade = scores?.grade || 'N/A';
  const gradeStyle = GRADE_COLORS[grade] || GRADE_COLORS['B'];
  const gradeLabel = GRADE_LABELS[grade] || '未知';

  // Dimensions to display in the breakdown bar
  const dimensions = [
    { key: 'skill_score', weight: 30 },
    { key: 'experience_score', weight: 20 },
    { key: 'education_score', weight: 10 },
    { key: 'responsibility_score', weight: 20 },
    { key: 'soft_skill_score', weight: 10 },
    { key: 'bonus_score', weight: 10 },
  ];

  return (
    <div className="fit-analysis-panel">
      {/* Score Card */}
      {scores && scores.total_score > 0 && (
        <div className="fit-score-card" style={{
          background: gradeStyle.bg,
          border: `2px solid ${gradeStyle.border}`,
          borderRadius: '16px',
          padding: '24px',
          marginBottom: '16px',
          textAlign: 'center',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '24px', flexWrap: 'wrap' }}>
            {/* Big Score Circle */}
            <div style={{
              width: '100px',
              height: '100px',
              borderRadius: '50%',
              background: 'white',
              border: `4px solid ${gradeStyle.border}`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
            }}>
              <span style={{ fontSize: '2rem', fontWeight: 'bold', color: gradeStyle.text, lineHeight: 1 }}>
                {scores.total_score}
              </span>
              <span style={{ fontSize: '0.7rem', color: gradeStyle.text }}>/100</span>
            </div>

            {/* Grade & Label */}
            <div style={{ textAlign: 'left' }}>
              <div style={{
                fontSize: '3rem',
                fontWeight: 'bold',
                color: gradeStyle.text,
                lineHeight: 1,
              }}>
                {grade}
              </div>
              <div style={{ fontSize: '1rem', color: gradeStyle.text, marginTop: '4px' }}>
                {gradeLabel}
              </div>
            </div>
          </div>

          {/* Dimension Breakdown Bars */}
          <div style={{ marginTop: '20px', display: 'grid', gap: '10px' }}>
            {dimensions.map(({ key, weight }) => {
              const value = scores[key] || 0;
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    width: '80px',
                    textAlign: 'right',
                    fontSize: '0.85rem',
                    color: '#495057',
                    fontWeight: 500
                  }}>
                    {DIMENSION_LABELS[key]}
                  </span>
                  <span style={{
                    width: '28px',
                    fontSize: '0.75rem',
                    color: '#6c757d',
                  }}>
                    {weight}%
                  </span>
                  <div style={{
                    flex: 1,
                    height: '10px',
                    background: '#e9ecef',
                    borderRadius: '5px',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      width: `${value}%`,
                      height: '100%',
                      background: value >= 80 ? '#28a745' : value >= 60 ? '#ffc107' : '#dc3545',
                      borderRadius: '5px',
                      transition: 'width 0.8s ease',
                    }} />
                  </div>
                  <span style={{
                    width: '40px',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    color: value >= 80 ? '#28a745' : value >= 60 ? '#856404' : '#dc3545',
                  }}>
                    {value}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Full Analysis Text (if no scores extracted, show raw) */}
      {analysis && !(scores && scores.total_score > 0) && (
        <div className="fit-analysis-raw" style={{
          background: 'white',
          padding: '16px',
          borderRadius: '12px',
          lineHeight: 1.7,
          fontSize: '0.95rem',
        }}>
          <div style={{ whiteSpace: 'pre-wrap' }}>{analysis}</div>
        </div>
      )}
    </div>
  );
};

export default FitAnalysis;
