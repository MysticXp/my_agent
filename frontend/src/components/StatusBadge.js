import React from 'react';

const STATUS_MAP = {
  idle: { label: '待命', color: '#6b7280' },
  planning: { label: '规划中', color: '#3b82f6' },
  executing: { label: '执行中', color: '#f59e0b' },
  interviewing: { label: '面试中', color: '#8b5cf6' },
  finished: { label: '已完成', color: '#10b981' },
  error: { label: '异常', color: '#ef4444' },
};

const StatusBadge = ({ status }) => {
  const info = STATUS_MAP[status] || STATUS_MAP.idle;
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: '12px',
        background: info.color,
        color: 'white',
        padding: '4px 12px',
        borderRadius: '20px',
        marginLeft: '10px',
      }}
    >
      {info.label}
    </span>
  );
};

export default StatusBadge;
