import React, { useState, useRef, useCallback } from 'react';
import { uploadResume } from '../api/client';

const ChatInput = ({ onSubmit, resume, setResume, jd, setJd, loading }) => {
  const [message, setMessage] = useState('我是Java后端，5年经验，想找远程工作，帮我分析市场机会并准备面试');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(message);
    setMessage('');
  };

  // 处理 PDF 上传
  const handleFileUpload = useCallback(async (file) => {
    if (!file) return;

    // 校验
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('仅支持 PDF 文件格式');
      setUploadSuccess('');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('文件大小超过 10MB 限制');
      setUploadSuccess('');
      return;
    }

    setUploading(true);
    setUploadError('');
    setUploadSuccess('');

    try {
      const result = await uploadResume(file);
      if (result.text) {
        setResume(result.text);
        setUploadSuccess(`解析成功！${result.pages || '?'}页，${result.char_count || 0}字`);
      }
    } catch (err) {
      const msg = typeof err === 'string' ? err : (err?.detail || err?.message || '上传失败');
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  }, [setResume]);

  // 拖拽事件
  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };
  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };
  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  };

  // 文件选择
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) handleFileUpload(file);
    // 重置 input 以便重复上传同一文件
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="input-area">
      <form onSubmit={handleSubmit}>
        {/* 简历：拖拽上传 + 手动编辑 */}
        <div className="input-group">
          <label>📄 简历 {uploading && '(解析中...)'}</label>

          {/* 上传区域 */}
          <div
            className={`upload-zone ${dragOver ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            {uploading ? (
              <span>⏳ 正在解析 PDF...</span>
            ) : (
              <span>📁 拖拽 PDF 简历到此处，或 <u>点击选择文件</u></span>
            )}
          </div>

          {/* 上传状态提示 */}
          {uploadError && (
            <div style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px' }}>
              ❌ {uploadError}
            </div>
          )}
          {uploadSuccess && (
            <div style={{ color: '#28a745', fontSize: '0.85rem', marginTop: '4px' }}>
              ✅ {uploadSuccess}（可在下方编辑）
            </div>
          )}

          {/* 简历文本编辑区 */}
          <textarea
            rows="6"
            placeholder="粘贴简历文本，或上传 PDF 自动解析..."
            value={resume}
            onChange={(e) => setResume(e.target.value)}
            className="input-textarea"
            style={{ marginTop: '8px' }}
          />
        </div>

        <div className="input-group">
          <label>📋 目标岗位JD</label>
          <textarea
            rows="6"
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