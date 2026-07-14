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
  const abortRef = useRef(null);

  // SSE 流式提交（优先使用）
  const submitStream = useCallback(async (payload) => {
    setLoading(true);
    setStreaming(true);

    if (payload.message) {
      setConversation(prev => [...prev, { role: 'user', content: payload.message }]);
    }
    if (payload.answer) {
      setConversation(prev => [...prev, { role: 'user', content: payload.answer }]);
    }

    abortRef.current = streamChat('/chat/stream', payload, {
      onNodeStart: (node, label) => {
        setConversation(prev => [...prev, { role: 'progress', content: `⏳ ${label}...`, status: 'thinking' }]);
      },
      onNodeEnd: () => {
        setConversation(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'progress') {
              updated[i] = { ...updated[i], status: 'done' };
              break;
            }
          }
          return updated;
        });
      },
      onToken: (token) => {
        setConversation(prev => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].role === 'assistant' && updated[i].streaming) {
              updated[i] = { ...updated[i], content: updated[i].content + token };
              return updated;
            }
          }
          updated.push({ role: 'assistant', content: token, streaming: true });
          return updated;
        });
      },
      onInterrupt: (data) => {
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
        setStatus('finished');
        setReport(data);
        if (data.fit_scores) setFitScores(data.fit_scores);
        if (data.fit_analysis) setFitAnalysis(data.fit_analysis);
        if (data.feedback) {
          data.feedback.forEach(f => setConversation(prev => [...prev, { role: 'assistant', content: f }]));
        }
        if (data.output) {
          setConversation(prev => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant' && updated[i].streaming) {
                updated[i] = { role: 'assistant', content: data.output };
                return updated;
              }
            }
            return [...prev, { role: 'assistant', content: data.output }];
          });
        }
        setCurrentQuestion(null);
      },
      onError: (err) => {
        setLoading(false);
        setStreaming(false);
        setStatus('error');
        setConversation(prev => [...prev, { role: 'error', content: err }]);
      },
    });
  }, []);

  // 启动面试或提交答案（优先流式，回退同步）
  const submit = useCallback(async (payload) => {
    setLoading(true);
    try {
      if (payload.message) {
        setConversation(prev => [...prev, { role: 'user', content: payload.message }]);
      }
      if (payload.answer) {
        setConversation(prev => [...prev, { role: 'user', content: payload.answer }]);
      }

      // 非 answer-only 的请求走流式
      if (payload.message) {
        submitStream(payload);
        return;
      }

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

  // 契合度审查：用户决定是否继续面试
  const decideInterview = useCallback(async (decision) => {
    setLoading(true);
    try {
      setConversation(prev => [...prev, { role: 'user', content: decision === 'continue' ? '继续面试' : '跳过面试' }]);
      const data = await sendMessage({ answer: decision });

      if (data.status === 'interviewing') {
        setStatus('interviewing');
        setCurrentQuestion(data.question);
        setQuestionNum(data.question_num);
        setTotalQuestions(data.total);
        setConversation(prev => [...prev, { role: 'assistant', content: `Q${data.question_num}: ${data.question}` }]);
      } else if (data.status === 'finished') {
        setStatus('finished');
        setReport(data);
        if (data.fit_scores) setFitScores(data.fit_scores);
        if (data.fit_analysis) setFitAnalysis(data.fit_analysis);
        if (data.similar_jds) setSimilarJds(data.similar_jds);
        if (data.similar_questions) setSimilarQuestions(data.similar_questions);
        if (data.feedback) {
          data.feedback.forEach(f => {
            setConversation(prev => [...prev, { role: 'assistant', content: f }]);
          });
        }
        if (data.output) {
          setConversation(prev => [...prev, { role: 'assistant', content: data.output }]);
        }
        setCurrentQuestion(null);
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
    submit,
    decideInterview,
    reset,
  };
};