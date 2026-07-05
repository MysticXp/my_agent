import React, { useState } from 'react';

const InterviewPanel = ({ question, questionNum, total, onSubmitAnswer, loading }) => {
  const [answer, setAnswer] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!answer.trim()) return;
    onSubmitAnswer(answer);
    setAnswer('');
  };

  return (
    <div className="interview-panel">
      <div className="question-box">
        <h3>面试题 {questionNum}/{total}</h3>
        <p style={{ fontSize: '1.1rem', background: '#f0f4ff', padding: '12px', borderRadius: '8px' }}>
          {question}
        </p>
      </div>
      <form onSubmit={handleSubmit} style={{ marginTop: '16px' }}>
        <textarea
          rows="3"
          placeholder="输入你的回答..."
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          disabled={loading}
          className="input-textarea"
        />
        <button type="submit" disabled={loading || !answer.trim()}>
          {loading ? '提交中...' : '📤 提交回答'}
        </button>
      </form>
    </div>
  );
};

export default InterviewPanel;