import React, { useState, useRef, useCallback } from 'react';
import { uploadResume, rematchResume } from '../api/client';

const ChatInput = ({ onSubmit, resume, setResume, jd, setJd, company, setCompany, role, setRole, loading }) => {
  const [message, setMessage] = useState('我是Java后端，5年经验，想找远程工作，帮我分析市场机会并准备面试');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [rematching, setRematching] = useState(false);
  const [rematchResults, setRematchResults] = useState(null);
  const [rematchError, setRematchError] = useState('');
  const fileInputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(message, company, role);
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

  // 重新匹配：用当前简历与所有历史 JD 做向量相似度对比
  const handleRematch = async () => {
    if (!resume || resume.length < 20) {
      setRematchError('简历文本太短（至少20字符）');
      return;
    }
    setRematching(true);
    setRematchError('');
    setRematchResults(null);
    try {
      const data = await rematchResume(resume);
      setRematchResults(data);
    } catch (err) {
      setRematchError(typeof err === 'string' ? err : (err?.detail || err?.message || '匹配失败'));
    } finally {
      setRematching(false);
    }
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
            onChange={(e) => {
              setResume(e.target.value);
              setRematchResults(null);
              setRematchError('');
            }}
            className="input-textarea"
            style={{ marginTop: '8px', height: '500px' }}
          />

          {/* 向量匹配历史JD按钮 */}
          {resume.length >= 20 && (
            <div style={{ marginTop: '8px' }}>
              <button
                type="button"
                onClick={handleRematch}
                disabled={rematching}
                style={{
                  fontSize: '0.85rem',
                  padding: '8px 16px',
                  background: rematching ? '#6c757d' : '#6610f2',
                }}
              >
                {rematching ? '⏳ 向量匹配中...' : '🔍 向量匹配历史JD'}
              </button>
              {rematchError && (
                <span style={{ color: '#dc3545', fontSize: '0.85rem', marginLeft: '10px' }}>
                  ❌ {rematchError}
                </span>
              )}
            </div>
          )}

          {/* 匹配结果 */}
          {rematchResults && rematchResults.matches && (
            <div style={{
              marginTop: '8px',
              padding: '12px',
              background: '#f8f9fa',
              borderRadius: '8px',
              maxHeight: '280px',
              overflowY: 'auto',
            }}>
              <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '8px' }}>
                📊 与 {rematchResults.total_jds_in_index || 0} 条历史 JD 的向量相似度排序：
              </div>
              {rematchResults.matches.map((m, idx) => (
                <div key={m.id || idx} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 0',
                  borderBottom: idx < rematchResults.matches.length - 1 ? '1px solid #e9ecef' : 'none',
                  fontSize: '0.8rem',
                }}>
                  <span style={{
                    width: '20px',
                    height: '20px',
                    borderRadius: '50%',
                    background: idx < 3 ? '#6610f2' : '#adb5bd',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.65rem',
                    fontWeight: 'bold',
                    flexShrink: 0,
                  }}>
                    {idx + 1}
                  </span>
                  <span style={{ fontWeight: 600, flex: 1 }}>
                    {m.company || '?'} — {m.role || '?'}
                  </span>
                  <span style={{
                    fontWeight: 700,
                    color: m.score >= 75 ? '#28a745' : m.score >= 55 ? '#856404' : '#6c757d',
                    flexShrink: 0,
                  }}>
                    {m.score}%
                  </span>
                </div>
              ))}
              {(!rematchResults.matches || rematchResults.matches.length === 0) && (
                <div style={{ color: '#6c757d', fontSize: '0.85rem' }}>
                  暂无历史JD，请先完成一次完整的 JD 分析
                </div>
              )}
            </div>
          )}
        </div>

        <div className="input-group">
          <label>📋 目标岗位JD</label>

          {/* 公司名 + 岗位名 */}
          <div style={{ display: 'flex', gap: '10px', marginBottom: '8px' }}>
            <input
              type="text"
              placeholder="公司名称（如：字节跳动）"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="input-text"
              style={{ flex: 1 }}
            />
            <input
              type="text"
              placeholder="岗位名称（如：高级前端开发工程师）"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="input-text"
              style={{ flex: 2 }}
            />
          </div>

          {/* JD 文本 */}
          <textarea
            rows="6"
            placeholder="粘贴职位描述（JD）..."
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            style={{ height: '500px' }}
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