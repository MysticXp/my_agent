import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// 核心请求：支持首次启动和后续回答
export const sendMessage = async (payload) => {
  try {
    const response = await client.post('/chat', payload);
    return response.data;
  } catch (error) {
    console.error('API Error:', error);
    throw error.response?.data || error.message;
  }
};

// 上传 PDF 简历并返回解析文本
export const uploadResume = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await client.post('/upload-resume', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,  // 30s 超时，大文件需要更长时间
    });
    return response.data;
  } catch (error) {
    console.error('Upload Error:', error);
    throw error.response?.data || error.message;
  }
};

// 重新匹配：用新简历对所有历史 JD 做向量相似度排序
export const rematchResume = async (resumeText) => {
  try {
    const response = await client.post('/rematch', { resume: resumeText });
    return response.data;
  } catch (error) {
    console.error('Rematch Error:', error);
    throw error.response?.data || error.message;
  }
};

// 获取向量库统计
export const getVectorStats = () => client.get('/vector-stats').then(r => r.data);

// 健康检查（可选）
export const healthCheck = () => client.get('/health');