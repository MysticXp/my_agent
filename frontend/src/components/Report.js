import React from 'react';
import Markdown from 'react-markdown';

const Report = ({ report }) => {
  return (
    <div className="report-panel">
      <h2>📊 面试报告 & 求职建议</h2>
      <div className="report-content">
        {report.output && <Markdown>{report.output}</Markdown>}
        {report.feedback && report.feedback.length > 0 && (
          <div className="feedback-section">
            <h3>📝 逐题反馈</h3>
            <ul>
              {report.feedback.map((f, idx) => (
                <li key={idx}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default Report;