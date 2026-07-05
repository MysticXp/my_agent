import React from 'react';

const ChatInput = ({ onSubmit, resume, setResume, jd, setJd, loading }) => {
  const [message, setMessage] = React.useState('我是Java后端，5年经验，想找远程工作，帮我分析市场机会并准备面试');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(message);
    setMessage('');
  };

  return (
    <div className="input-area">
      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label>📄 简历</label>
          <textarea
            rows="4"
            placeholder="粘贴你的简历文本..."
            value={resume}
            onChange={(e) => setResume(e.target.value)}
            className="input-textarea"
          />
        </div>
        <div className="input-group">
          <label>📋 目标岗位JD</label>
          <textarea
            rows="4"
            placeholder="粘贴职位描述（JD）..."
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            className="input-textarea"
          />
        </div>
        <div className="input-group">
          <label>💬 你的求职需求</label>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              placeholder="如：帮我优化简历并模拟面试"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              className="input-text"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !message.trim()}>
              {loading ? '处理中...' : '🚀 开始'}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default ChatInput;