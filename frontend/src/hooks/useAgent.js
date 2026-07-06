import { useState, useCallback } from 'react';
import { sendMessage } from '../api/client';

export const useAgent = () => {
  const [status, setStatus] = useState('idle'); // idle | interviewing | finished | error
  const [conversation, setConversation] = useState([]); // [{role:'user'|'assistant', content}]
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNum, setQuestionNum] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [report, setReport] = useState(null);
  const [fitScores, setFitScores] = useState(null);
  const [fitAnalysis, setFitAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  // 启动面试或提交答案
  const submit = useCallback(async (payload) => {
    setLoading(true);
    try {
      // 如果是首次，记录用户消息
      if (payload.message) {
        setConversation(prev => [...prev, { role: 'user', content: payload.message }]);
      }
      // 如果有答案，记录用户的回答
      if (payload.answer) {
        setConversation(prev => [...prev, { role: 'user', content: payload.answer }]);
      }

      const data = await sendMessage(payload);

      if (data.status === 'interviewing') {
        // 面试进行中
        setStatus('interviewing');
        setCurrentQuestion(data.question);
        setQuestionNum(data.question_num);
        setTotalQuestions(data.total);
        setConversation(prev => [...prev, { role: 'assistant', content: `Q${data.question_num}: ${data.question}` }]);
      } else if (data.status === 'finished') {
        // 面试完成，获取报告
        setStatus('finished');
        setReport(data);
        // 保存契合度分析数据
        if (data.fit_scores) {
          setFitScores(data.fit_scores);
        }
        if (data.fit_analysis) {
          setFitAnalysis(data.fit_analysis);
        }
        // 添加反馈到对话
        if (data.feedback) {
          data.feedback.forEach(f => {
            setConversation(prev => [...prev, { role: 'assistant', content: f }]);
          });
        }
        if (data.output) {
          setConversation(prev => [...prev, { role: 'assistant', content: data.output }]);
        }
        setCurrentQuestion(null);
      } else {
        setStatus('error');
        setConversation(prev => [...prev, { role: 'error', content: data.detail || '未知错误' }]);
      }
    } catch (error) {
      setStatus('error');
      setConversation(prev => [...prev, { role: 'error', content: error.message || '网络错误' }]);
    } finally {
      setLoading(false);
    }
  }, []);

  // 重置状态
  const reset = useCallback(() => {
    setStatus('idle');
    setConversation([]);
    setCurrentQuestion(null);
    setQuestionNum(0);
    setTotalQuestions(0);
    setReport(null);
    setFitScores(null);
    setFitAnalysis(null);
    setLoading(false);
  }, []);

  return {
    status,
    conversation,
    currentQuestion,
    questionNum,
    totalQuestions,
    report,
    fitScores,
    fitAnalysis,
    loading,
    submit,
    reset,
  };
};