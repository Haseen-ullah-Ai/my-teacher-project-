import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DataTable } from './DataTable';

interface Row {
  id: number;
  name: string;
}

const columns = [
  { key: 'name', label: 'Name', render: (row: Row) => row.name, sortValue: (row: Row) => row.name },
];

describe('DataTable', () => {
  it('sorts rows by a sortable column and fires row clicks', () => {
    const onRowClick = vi.fn();
    render(<DataTable rows={[{ id: 1, name: 'Zephyr' }, { id: 2, name: 'Atlas' }]} columns={columns} rowKey={(row) => String(row.id)} onRowClick={onRowClick} />);

    fireEvent.click(screen.getByRole('button', { name: /Name/ }));
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('Atlas');
    fireEvent.click(screen.getByRole('row', { name: /Atlas/ }));
    expect(onRowClick).toHaveBeenCalledWith({ id: 2, name: 'Atlas' });
  });

  it('shows the empty state when there are no rows', () => {
    render(<DataTable rows={[]} columns={columns} rowKey={(row) => String(row.id)} emptyTitle="No records" emptyDescription="Upload a file to begin." />);
    expect(screen.getByText('No records')).toBeInTheDocument();
  });
});
