import React, { useState } from 'react';
import { useAgent } from '../hooks/useAgent';
import ChatInput from './ChatInput';
import InterviewPanel from './InterviewPanel';
import Report from './Report';
import FitAnalysis from './FitAnalysis';
import FitReviewPanel from './FitReviewPanel';
import StatusBadge from './StatusBadge';
import '../styles/App.css';

function App() {
  const {
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
    submit,
    decideInterview,
    reset,
  } = useAgent();

  const [resume, setResume] = useState('5年Java经验，Spring Cloud，高并发项目经验');
  const [company, setCompany] = useState('字节跳动');
  const [role, setRole] = useState('高级前端开发工程师');
  const [jd, setJd] = useState(`岗位名称：高级前端开发工程师
公司：字节跳动（ByteDance）
地点：上海

岗位职责：
1. 负责公司核心中后台系统的前端架构设计与开发，包括但不限于数据可视化大屏、低代码搭建平台、运营管理系统。
2. 主导前端工程化建设，制定代码规范、构建流程、自动化测试方案，持续提升团队交付质量。
3. 深入参与产品需求评审，与产品、设计、后端紧密协作，推动复杂交互方案的落地。
4. 优化首屏加载性能、打包体积、运行时渲染效率，确保系统在百万级数据量下依然流畅。
5. 指导初中级工程师成长，组织技术分享，撰写高质量技术文档。

任职要求：
1. 5年以上前端开发经验，计算机相关专业本科及以上学历。
2. 精通 React 全家桶（Hooks、Context、Suspense、React Router），熟悉源码级原理。
3. 精通 TypeScript，具备大型项目类型系统设计经验。
4. 深入理解 Webpack/Vite 等构建工具，有实际的性能优化经验（Core Web Vitals 指标提升）。
5. 熟悉 Node.js 服务端开发，有 BFF 层或全栈项目经验。
6. 具备良好的数据结构和算法基础，能独立解决复杂技术问题。
7. 有中大型前端团队技术管理或 Tech Lead 经验者优先。
8. 有 AI 相关产品开发经验（如对接大模型 API、智能对话系统）者优先。

薪资范围：35k-55k·15薪`);

  // 处理用户首次提交（消息+简历+JD+公司+岗位）
  const handleInitialSubmit = (message, companyName, roleName) => {
    if (!message.trim()) return;
    submit({
      message,
      resume,
      job_description: jd,
      company: companyName || company,
      role: roleName || role,
    });
  };

  // 处理面试答案提交
  const handleAnswerSubmit = (answer) => {
    if (!answer.trim()) return;
    submit({ answer });
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>🤖 求职AI助手</h1>
        <StatusBadge status={status} />
        {status !== 'idle' && (
          <button onClick={reset} className="reset-btn">🔄 重新开始</button>
        )}
      </header>

      <main className="app-main">
        {/* 输入区：仅在空闲状态显示 */}
        {status === 'idle' && (
          <ChatInput
            onSubmit={handleInitialSubmit}
            resume={resume}
            setResume={setResume}
            jd={jd}
            setJd={setJd}
            company={company}
            setCompany={setCompany}
            role={role}
            setRole={setRole}
            loading={loading}
          />
        )}

        {/* 对话/面试区 */}
        {(status === 'fit_review' || status === 'interviewing' || status === 'finished') && (
          <div className="conversation-area">
            <div className="conversation-log">
              {conversation.map((msg, idx) => (
                <div key={idx} className={`message ${msg.role}`}>
                  <div className="message-content">
                    <strong>{msg.role === 'user' ? '你' : '助手'}:</strong>
                    <pre style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</pre>
                  </div>
                </div>
              ))}
              {loading && <div className="message assistant"><div className="message-content">⏳ 思考中...</div></div>}
            </div>

            {/* 契合度审查：等用户决定是否继续 */}
            {status === 'fit_review' && (
              <FitReviewPanel
                fitScores={fitScores}
                fitAnalysis={fitAnalysis}
                similarJds={similarJds}
                similarQuestions={similarQuestions}
                onDecide={decideInterview}
                loading={loading}
              />
            )}

            {/* 面试进行中：显示当前题目和输入框 */}
            {status === 'interviewing' && currentQuestion && (
              <InterviewPanel
                question={currentQuestion}
                questionNum={questionNum}
                total={totalQuestions}
                onSubmitAnswer={handleAnswerSubmit}
                loading={loading}
              />
            )}

            {/* 面试结束：显示契合度分析 + 报告 */}
            {status === 'finished' && (
              <>
                <FitAnalysis scores={fitScores} analysis={fitAnalysis} />
                {report && <Report report={report} />}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;