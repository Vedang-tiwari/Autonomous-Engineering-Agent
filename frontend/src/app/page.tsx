'use client';

import React, { useState, useEffect, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PlanStep {
  step_number: number;
  title: string;
  description: string;
  status: string;
}

interface ExecutionPlan {
  overview: string;
  steps: PlanStep[];
}

interface FileChange {
  path: string;
  action: string;
  diff: string;
  lines_added: number;
  lines_removed: number;
}

interface TestResult {
  command: string;
  exit_code: number;
  passed: boolean;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  duration_seconds: number;
  stdout: string;
  stderr: string;
  failures_summary: string[];
}

interface ReviewResult {
  decision: string;
  summary: string;
  quality_score: number;
  issues: string[];
  security_concerns: string[];
  regression_risk: string;
  recommendations?: string;
}

interface PullRequestInfo {
  title: string;
  body: string;
  branch_name: string;
  commit_sha?: string;
  pr_url?: string;
}

interface Task {
  task_id: string;
  repository: string;
  task: string;
  status: string;
  current_step?: string;
  iteration: number;
  max_iterations: number;
  plan?: ExecutionPlan;
  files_changed: FileChange[];
  test_result?: TestResult;
  review?: ReviewResult;
  pull_request?: PullRequestInfo;
  created_at: string;
}

interface LogEvent {
  timestamp: string;
  step: string;
  status: string;
  message: string;
  event: string;
}

const PIPELINE_STEPS = [
  { id: 'planning', label: '1. Plan' },
  { id: 'repository_analysis', label: '2. Analyze' },
  { id: 'retrieval', label: '3. Retrieve' },
  { id: 'coding', label: '4. Code' },
  { id: 'testing', label: '5. Sandbox' },
  { id: 'review', label: '6. Review' },
  { id: 'git', label: '7. Git & PR' },
];

export default function Dashboard() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [activeTab, setActiveTab] = useState<'plan' | 'diffs' | 'tests' | 'review' | 'pr'>('plan');

  // Form inputs
  const [repoInput, setRepoInput] = useState('https://github.com/example/payment-api');
  const [taskInput, setTaskInput] = useState('Find the cause of the failing duplicate payment transactions, fix the issue, add regression tests, and prepare a Pull Request.');
  const [requireApproval, setRequireApproval] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Fetch past tasks on mount
  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 6000);
    return () => clearInterval(interval);
  }, []);

  const fetchTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tasks`);
      if (res.ok) {
        const data: Task[] = await res.json();
        setTasks(data);
        // If no active task selected and we have tasks, select the first
        if (!activeTask && data.length > 0) {
          setActiveTask(data[0]);
        } else if (activeTask) {
          // Update active task if it was updated in backend
          const updated = data.find((t) => t.task_id === activeTask.task_id);
          if (updated) {
            setActiveTask(updated);
          }
        }
      }
    } catch (e) {
      // Backend not yet reached or starting up
    }
  };

  // Subscribe to SSE when activeTask changes
  useEffect(() => {
    if (!activeTask) return;

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setLogs([]);
    const sse = new EventSource(`${API_BASE}/api/tasks/${activeTask.task_id}/events`);
    eventSourceRef.current = sse;

    const handleEvent = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setLogs((prev) => [...prev, data]);
        // Re-fetch task state
        fetchTaskDetail(activeTask.task_id);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    };

    sse.onmessage = handleEvent;
    sse.onerror = () => {
      sse.close();
    };

    // Listen to custom event types
    PIPELINE_STEPS.forEach((step) => {
      sse.addEventListener(step.id, handleEvent);
    });
    sse.addEventListener('task_completed', handleEvent);
    sse.addEventListener('task_failed', handleEvent);

    return () => {
      sse.close();
    };
  }, [activeTask?.task_id]);

  // Auto-scroll terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const fetchTaskDetail = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/tasks/${id}`);
      if (res.ok) {
        const data: Task = await res.json();
        setActiveTask(data);
      }
    } catch (e) {}
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await fetch(`${API_BASE}/api/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository: repoInput,
          task: taskInput,
          require_human_approval: requireApproval,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const result = await res.json();
      await fetchTasks();
      // Fetch new task detail
      await fetchTaskDetail(result.task_id);
    } catch (err: any) {
      setErrorMsg(`Failed to launch task: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!activeTask) return;
    try {
      await fetch(`${API_BASE}/api/tasks/${activeTask.task_id}/approve`, {
        method: 'POST',
      });
      fetchTaskDetail(activeTask.task_id);
    } catch (e) {
      console.error(e);
    }
  };

  const handlePreset = (repo: string, goal: string) => {
    setRepoInput(repo);
    setTaskInput(goal);
  };

  // Helper for pipeline step status
  const getStepStatus = (stepId: string) => {
    if (!activeTask) return 'pending';
    const status = activeTask.status.toLowerCase();
    const current = activeTask.current_step?.toLowerCase() || '';

    if (status === 'completed') return 'completed';
    if (current.includes(stepId)) return 'active';

    const stepOrder = ['planning', 'repository_analysis', 'retrieval', 'coding', 'testing', 'review', 'git'];
    const currentIndex = stepOrder.findIndex((s) => current.includes(s));
    const thisIndex = stepOrder.findIndex((s) => s === stepId);

    if (currentIndex > thisIndex) return 'completed';
    return 'pending';
  };

  return (
    <div className="dashboard-container">
      {/* LEFT COLUMN: Controls & Task History */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Task Submission Card */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>⚡</span> Submit Engineering Task
          </h2>

          <form onSubmit={handleCreateTask}>
            <div className="form-group">
              <label className="form-label">Repository (Git URL or Local Path)</label>
              <input
                type="text"
                className="form-input"
                value={repoInput}
                onChange={(e) => setRepoInput(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Engineering Goal / Objective</label>
              <textarea
                className="form-textarea"
                value={taskInput}
                onChange={(e) => setTaskInput(e.target.value)}
                required
              />
            </div>

            {/* Quick-fill Presets */}
            <div style={{ marginBottom: '1.2rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.4rem' }}>
                Quick Presets:
              </span>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() =>
                    handlePreset(
                      'https://github.com/example/payment-api',
                      'Find the cause of duplicate payment requests, fix idempotency in payment service, and add regression tests.'
                    )
                  }
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    borderRadius: '4px',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  💳 Duplicate Payment Bug
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handlePreset(
                      'https://github.com/example/auth-service',
                      'Find why expired JWT tokens crash the middleware, return HTTP 401 instead, and add regression tests.'
                    )
                  }
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    borderRadius: '4px',
                    padding: '0.25rem 0.5rem',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  🔑 Expired JWT Fix
                </button>
              </div>
            </div>

            <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="checkbox"
                id="approval-check"
                checked={requireApproval}
                onChange={(e) => setRequireApproval(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <label htmlFor="approval-check" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                Require Human Approval before PR
              </label>
            </div>

            {errorMsg && (
              <div style={{ color: 'var(--accent-rose)', fontSize: '0.82rem', marginBottom: '1rem' }}>
                {errorMsg}
              </div>
            )}

            <button type="submit" className="btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Launching Agent Loop...' : '🚀 Launch Autonomous Workflow'}
            </button>
          </form>
        </div>

        {/* Task Runs List */}
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.85rem', display: 'flex', justifyContent: 'space-between' }}>
            <span>Recent Agent Executions</span>
            <span style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>{tasks.length} total</span>
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '350px', overflowY: 'auto' }}>
            {tasks.length === 0 ? (
              <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>
                No tasks executed yet. Submit one above!
              </div>
            ) : (
              tasks.map((t) => {
                const isSelected = activeTask?.task_id === t.task_id;
                return (
                  <div
                    key={t.task_id}
                    onClick={() => setActiveTask(t)}
                    style={{
                      padding: '0.75rem',
                      borderRadius: '8px',
                      background: isSelected ? 'var(--bg-tertiary)' : 'rgba(15, 23, 42, 0.4)',
                      border: isSelected ? '1px solid var(--accent-indigo)' : '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>
                        {t.task_id}
                      </span>
                      <span
                        style={{
                          fontSize: '0.72rem',
                          textTransform: 'uppercase',
                          fontWeight: 600,
                          color:
                            t.status === 'completed'
                              ? 'var(--accent-green)'
                              : t.status === 'failed'
                              ? 'var(--accent-rose)'
                              : 'var(--accent-amber)',
                        }}
                      >
                        {t.status}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: '0.82rem',
                        color: 'var(--text-secondary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {t.task}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* RIGHT COLUMN: Real-Time Execution View */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Active Task Details & Pipeline */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          {activeTask ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.2rem' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
                    <h1 style={{ fontSize: '1.25rem', fontWeight: 600 }}>{activeTask.task_id}</h1>
                    <span
                      style={{
                        background:
                          activeTask.status === 'completed'
                            ? 'rgba(16, 185, 129, 0.15)'
                            : activeTask.status === 'failed'
                            ? 'rgba(244, 63, 94, 0.15)'
                            : 'rgba(99, 102, 241, 0.15)',
                        color:
                          activeTask.status === 'completed'
                            ? 'var(--accent-green)'
                            : activeTask.status === 'failed'
                            ? 'var(--accent-rose)'
                            : 'var(--accent-indigo)',
                        padding: '0.2rem 0.6rem',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}
                    >
                      {activeTask.status}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      Iteration {activeTask.iteration} / {activeTask.max_iterations}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{activeTask.task}</p>
                </div>

                <div style={{ textAlign: 'right', fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {activeTask.repository}
                </div>
              </div>

              {/* Pipeline Stepper */}
              <div className="stepper">
                {PIPELINE_STEPS.map((step) => {
                  const status = getStepStatus(step.id);
                  return (
                    <div key={step.id} className={`step-node ${status}`}>
                      <div className="step-circle">
                        {status === 'completed' ? '✓' : status === 'active' ? '⟳' : '○'}
                      </div>
                      <span className="step-title">{step.label}</span>
                    </div>
                  );
                })}
              </div>

              {/* Human-in-the-Loop Banner if Awaiting Approval */}
              {activeTask.status === 'awaiting_approval' && (
                <div
                  style={{
                    background: 'rgba(245, 158, 11, 0.12)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    padding: '1rem 1.25rem',
                    borderRadius: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '1rem',
                  }}
                >
                  <div>
                    <h4 style={{ color: 'var(--accent-amber)', fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.2rem' }}>
                      ⚠️ Developer Approval Required
                    </h4>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      Sandbox tests have passed. Please review the code diff below and grant approval to commit and generate Pull Request.
                    </p>
                  </div>
                  <button
                    onClick={handleApprove}
                    style={{
                      background: 'var(--accent-green)',
                      color: '#000',
                      border: 'none',
                      padding: '0.6rem 1.25rem',
                      borderRadius: '6px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Approve & Create PR
                  </button>
                </div>
              )}

              {/* Live Terminal Console */}
              <div className="terminal-window">
                <div className="terminal-header">
                  <div className="terminal-dots">
                    <div className="terminal-dot red" />
                    <div className="terminal-dot yellow" />
                    <div className="terminal-dot green" />
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Live Event Stream: {activeTask.task_id}
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                    {logs.length} events
                  </span>
                </div>
                <div className="terminal-body">
                  {logs.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)' }}>Waiting for agent events...</div>
                  ) : (
                    logs.map((log, i) => (
                      <div key={i} className="log-entry">
                        <span className="log-time">{log.timestamp?.split('T')[1]?.split('.')[0] || 'NOW'}</span>
                        <span className="log-step">[{log.step}]</span>
                        <span className="log-msg">{log.message}</span>
                      </div>
                    ))
                  )}
                  <div ref={terminalEndRef} />
                </div>
              </div>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
              Select a task or launch a new engineering objective to monitor real-time agent execution.
            </div>
          )}
        </div>

        {/* Artifact Inspector Tabs */}
        {activeTask && (
          <div className="glass-panel" style={{ padding: '0 0 1.5rem 0' }}>
            <div className="tabs-header">
              <button
                className={`tab-btn ${activeTab === 'plan' ? 'active' : ''}`}
                onClick={() => setActiveTab('plan')}
              >
                📋 Execution Plan ({activeTask.plan?.steps?.length || 0})
              </button>
              <button
                className={`tab-btn ${activeTab === 'diffs' ? 'active' : ''}`}
                onClick={() => setActiveTab('diffs')}
              >
                🔍 Code Diffs ({activeTask.files_changed?.length || 0})
              </button>
              <button
                className={`tab-btn ${activeTab === 'tests' ? 'active' : ''}`}
                onClick={() => setActiveTab('tests')}
              >
                🧪 Sandbox Tests
              </button>
              <button
                className={`tab-btn ${activeTab === 'review' ? 'active' : ''}`}
                onClick={() => setActiveTab('review')}
              >
                🚦 Review Decision
              </button>
              <button
                className={`tab-btn ${activeTab === 'pr' ? 'active' : ''}`}
                onClick={() => setActiveTab('pr')}
              >
                📦 Pull Request
              </button>
            </div>

            <div style={{ padding: '0 1.5rem' }}>
              {/* PLAN TAB */}
              {activeTab === 'plan' && (
                <div>
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                    {activeTask.plan?.overview || 'Plan is being formulated by the Planning Agent...'}
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {activeTask.plan?.steps?.map((s) => (
                      <div
                        key={s.step_number}
                        style={{
                          background: 'var(--bg-secondary)',
                          padding: '0.85rem 1rem',
                          borderRadius: '8px',
                          border: '1px solid var(--border-subtle)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.2rem' }}>
                            Step {s.step_number}: {s.title}
                          </div>
                          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            {s.description}
                          </div>
                        </div>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: 'var(--accent-cyan)',
                            textTransform: 'uppercase',
                          }}
                        >
                          {s.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* DIFFS TAB */}
              {activeTab === 'diffs' && (
                <div>
                  {activeTask.files_changed?.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No file modifications registered yet.
                    </div>
                  ) : (
                    activeTask.files_changed.map((file, idx) => (
                      <div key={idx} style={{ marginBottom: '1.25rem' }}>
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            padding: '0.5rem 0',
                            borderBottom: '1px solid var(--border-subtle)',
                            marginBottom: '0.5rem',
                          }}
                        >
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
                            {file.path}
                          </span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            <span style={{ color: 'var(--accent-green)' }}>+{file.lines_added}</span> /{' '}
                            <span style={{ color: 'var(--accent-rose)' }}>-{file.lines_removed}</span>
                          </span>
                        </div>
                        <div className="diff-container">
                          {file.diff.split('\n').map((line, lIdx) => {
                            let className = 'diff-line';
                            if (line.startsWith('+') && !line.startsWith('+++')) className += ' add';
                            else if (line.startsWith('-') && !line.startsWith('---')) className += ' del';
                            else if (line.startsWith('@@')) className += ' header';
                            return (
                              <div key={lIdx} className={className}>
                                {line}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TESTS TAB */}
              {activeTab === 'tests' && (
                <div>
                  {activeTask.test_result ? (
                    <div>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(4, 1fr)',
                          gap: '1rem',
                          marginBottom: '1.2rem',
                        }}
                      >
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.85rem', borderRadius: '8px' }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status</span>
                          <div
                            style={{
                              fontSize: '1.1rem',
                              fontWeight: 700,
                              color: activeTask.test_result.passed ? 'var(--accent-green)' : 'var(--accent-rose)',
                            }}
                          >
                            {activeTask.test_result.passed ? 'PASSED' : 'FAILED'}
                          </div>
                        </div>
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.85rem', borderRadius: '8px' }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Passed / Total</span>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                            {activeTask.test_result.passed_tests} / {activeTask.test_result.total_tests}
                          </div>
                        </div>
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.85rem', borderRadius: '8px' }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Duration</span>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                            {activeTask.test_result.duration_seconds}s
                          </div>
                        </div>
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.85rem', borderRadius: '8px' }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Command</span>
                          <div
                            style={{
                              fontSize: '0.85rem',
                              fontFamily: 'var(--font-mono)',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {activeTask.test_result.command}
                          </div>
                        </div>
                      </div>

                      {/* Failures or Output */}
                      <div className="terminal-window">
                        <div className="terminal-header">
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sandbox Stdout / Output</span>
                        </div>
                        <pre style={{ padding: '0.85rem', fontSize: '0.8rem', maxHeight: '250px', overflowY: 'auto' }}>
                          {activeTask.test_result.stdout || activeTask.test_result.stderr || 'No output recorded.'}
                        </pre>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      Tests have not been executed yet.
                    </div>
                  )}
                </div>
              )}

              {/* REVIEW TAB */}
              {activeTab === 'review' && (
                <div>
                  {activeTask.review ? (
                    <div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '1rem',
                          marginBottom: '1rem',
                          padding: '1rem',
                          background: 'var(--bg-secondary)',
                          borderRadius: '8px',
                        }}
                      >
                        <div
                          style={{
                            width: '56px',
                            height: '56px',
                            borderRadius: '50%',
                            background:
                              activeTask.review.decision === 'APPROVED'
                                ? 'rgba(16, 185, 129, 0.2)'
                                : 'rgba(245, 158, 11, 0.2)',
                            color:
                              activeTask.review.decision === 'APPROVED'
                                ? 'var(--accent-green)'
                                : 'var(--accent-amber)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 700,
                            fontSize: '1.2rem',
                          }}
                        >
                          {activeTask.review.quality_score}
                        </div>
                        <div>
                          <div
                            style={{
                              fontWeight: 700,
                              fontSize: '1.1rem',
                              color:
                                activeTask.review.decision === 'APPROVED'
                                  ? 'var(--accent-green)'
                                  : 'var(--accent-amber)',
                            }}
                          >
                            Decision: {activeTask.review.decision}
                          </div>
                          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                            {activeTask.review.summary}
                          </p>
                        </div>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div style={{ background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '8px' }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                            Security Concerns
                          </span>
                          <div style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>
                            {activeTask.review.security_concerns.length === 0 ? (
                              <span style={{ color: 'var(--accent-green)' }}>✓ Zero security regressions identified.</span>
                            ) : (
                              activeTask.review.security_concerns.map((s, i) => <div key={i}>⚠️ {s}</div>)
                            )}
                          </div>
                        </div>

                        <div style={{ background: 'var(--bg-secondary)', padding: '1rem', borderRadius: '8px' }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                            Regression Hazard
                          </span>
                          <div style={{ fontSize: '0.85rem', marginTop: '0.5rem', textTransform: 'capitalize' }}>
                            Risk level: <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>{activeTask.review.regression_risk}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      Automated code review pending completion of tests.
                    </div>
                  )}
                </div>
              )}

              {/* PR TAB */}
              {activeTab === 'pr' && (
                <div>
                  {activeTask.pull_request ? (
                    <div style={{ background: 'var(--bg-secondary)', padding: '1.25rem', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                        <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>{activeTask.pull_request.title}</h3>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
                          Branch: {activeTask.pull_request.branch_name}
                        </span>
                      </div>
                      <pre
                        style={{
                          background: '#05070B',
                          padding: '1rem',
                          borderRadius: '6px',
                          fontSize: '0.82rem',
                          fontFamily: 'var(--font-mono)',
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.6,
                        }}
                      >
                        {activeTask.pull_request.body}
                      </pre>
                    </div>
                  ) : (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      Pull Request will be prepared upon passing test suite and review.
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
