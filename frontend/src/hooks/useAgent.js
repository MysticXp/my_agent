import { useState, useCallback, useRef } from 'react';
import { sendMessage } from '../api/client';
import { streamChat } from '../api/streamClient';

export const useAgent = () => {
  const [status, setStatus] = useState('idle'); // idle | interviewing | finished | error
  const [conversation, setConversation] = useState([]); // [{role:'user'|'assistant', content}]
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNum, setQuestionNum] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [report, setReport] = useState(null);
  const [fitScores, setFitScores] = useState(null);
  const [fitAnalysis, setFitAnalysis] = useState(null);
  const [similarJds, setSimilarJds] = useState([]);
  const [similarQuestions, setSimilarQuestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamReport, setStreamReport] = useState('');
  const [interviewAvailable, setInterviewAvailable] = useState(false);
  const [currentStep, setCurrentStep] = useState(''); // 当前执行步骤（如"分析需求"）
  const streamReportRef = useRef('');
  const abortRef = useRef(null);

  // SSE 流式提交（优先使用）
  const submitStream = useCallback(async (payload) => {
    setLoading(true);
    setStreaming(true);

    if (payload.message) {
      setConversation(prev => [...prev, { role: 'user', content: payload.message }]);
    }
    // answer 的消息由调用方（decideInterview / handleAnswerSubmit）自行记录

    abortRef.current = streamChat('/chat/stream', payload, {
      onNodeStart: (node, label) => { setCurrentStep(label); },
      onNodeEnd: () => {},
      onToken: (token) => {
        streamReportRef.current += token;
        setStreamReport(streamReportRef.current);
      },
      onInterrupt: (data) => {
        setStreamReport('');
        streamReportRef.current = '';
        setCurrentStep('');
        setLoading(false);
        setStreaming(false);
        if (data.type === 'fit_review') {
          setStatus('fit_review');
          if (data.fit_analysis) setFitAnalysis(data.fit_analysis);
          if (data.fit_scores) setFitScores(data.fit_scores);
          if (data.similar_jds) setSimilarJds(data.similar_jds);
          if (data.similar_questions) setSimilarQuestions(data.similar_questions);
          setConversation(prev => [...prev, { role: 'assistant', content: data.question || '契合度分析已完成，是否继续模拟面试？' }]);
        } else if (data.type === 'interview') {
          setStatus('interviewing');
          setCurrentQuestion(data.question);
          setQuestionNum(data.question_num);
          setTotalQuestions(data.total);
          setConversation(prev => [...prev, { role: 'assistant', content: `Q${data.question_num}: ${data.question}` }]);
        }
      },
      onDone: (data) => {
        setLoading(false);
        setStreaming(false);
        const finalOutput = streamReportRef.current || data.output || '';
        setStreamReport(''); // 清除流式预览，避免闪烁
        streamReportRef.current = '';
        setStatus('finished');
        setReport({ ...data, output: finalOutput });
        setFitScores(data.fit_scores || null);
        setFitAnalysis(data.fit_analysis || null);
        setInterviewAvailable(data.interview_available || false);
        if (data.feedback && data.feedback.length > 0) {
          setConversation(prev => {
            const existing = prev.map(m => m.content);
            const newItems = data.feedback.filter(f => !existing.includes(f));
            return [...prev, ...newItems.map(f => ({ role: 'assistant', content: f }))];
          });
        }
        setCurrentQuestion(null);
      },
      onError: (err) => {
        setStreamReport('');
        streamReportRef.current = '';
        setCurrentStep('');
        setLoading(false);
        setStreaming(false);
        setStatus('error');
        setConversation(prev => [...prev, { role: 'error', content: err }]);
      },
    });
  }, []);

  // 启动面试或提交答案（优先流式，回退同步）
  const submit = useCallback(async (payload) => {
    const userMsg = payload.message || payload.answer;
    if (userMsg) {
      setConversation(prev => [...prev, { role: 'user', content: userMsg }]);
    }

    // 有 message 或 answer 就走流式（submitStream 自己管理 loading）
    if (payload.message || payload.answer) {
      submitStream(payload);
      return;
    }

    // === 以下为同步回退（当前不会被走到，保留兼容） ===
    setLoading(true);
    try {
      const data = await sendMessage(payload);

      if (data.status === 'fit_review') {
        // 契合度审查暂停：等待用户决定是否继续面试
        setStatus('fit_review');
        if (data.fit_analysis) setFitAnalysis(data.fit_analysis);
        if (data.fit_scores) setFitScores(data.fit_scores);
        if (data.similar_jds) setSimilarJds(data.similar_jds);
        if (data.similar_questions) setSimilarQuestions(data.similar_questions);
        setConversation(prev => [...prev, { role: 'assistant', content: data.question || '契合度分析已完成，是否继续模拟面试？' }]);
      } else if (data.status === 'interviewing') {
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
        if (data.similar_jds) {
          setSimilarJds(data.similar_jds);
        }
        if (data.similar_questions) {
          setSimilarQuestions(data.similar_questions);
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

  // 契合度审查：用户决定是否继续面试（走 stream）
  const decideInterview = useCallback((decision) => {
    const display = decision === 'continue' ? '继续面试' : '跳过面试';
    setConversation(prev => [...prev, { role: 'user', content: display }]);
    submitStream({ answer: decision });
  }, [submitStream]);

  // 用户看完报告后请求开始模拟面试
  const startInterview = useCallback((params = {}) => {
    setConversation(prev => [...prev, { role: 'user', content: '开始模拟面试' }]);
    submitStream({
      interview_requested: true,
      resume: params.resume || '',
      job_description: params.jd || '',
      company: params.company || '',
      role: params.role || '',
      message: '开始模拟面试',
    });
  }, [submitStream]);

  // 重置状态
  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStatus('idle');
    setConversation([]);
    setCurrentQuestion(null);
    setQuestionNum(0);
    setTotalQuestions(0);
    setReport(null);
    setFitScores(null);
    setFitAnalysis(null);
    setSimilarJds([]);
    setSimilarQuestions([]);
    setLoading(false);
    setStreaming(false);
    setStreamReport('');
    streamReportRef.current = '';
    setInterviewAvailable(false);
    setCurrentStep('');
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
    similarJds,
    similarQuestions,
    loading,
    streaming,
    streamReport,
    interviewAvailable,
    currentStep,
    submit,
    decideInterview,
    startInterview,
    reset,
  };
};