import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { StatusBadge } from './ui';

describe('StatusBadge', () => {
  it('renders a readable completed status', () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText('completed')).toHaveClass('status-badge', 'status-completed');
  });

  it('marks active runs as running and announces the status', () => {
    render(<StatusBadge status="running" />);
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Running').querySelector('.status-pulse')).toBeInTheDocument();
  });
});
