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

// 健康检查（可选）
export const healthCheck = () => client.get('/health');