import { useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react';
import type { ReactNode } from 'react';
import { EmptyState } from './ui';

export interface TableColumn<T> {
  key: string;
  label: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number;
  className?: string;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  onRowClick,
  emptyTitle = 'Nothing here yet',
  emptyDescription = 'When items are available, they will appear here.',
}: {
  rows: T[];
  columns: TableColumn<T>[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  const [sortKey, setSortKey] = useState<string>();
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const column = columns.find((item) => item.key === sortKey);
    if (!column?.sortValue) return rows;
    return [...rows].sort((a, b) => {
      const left = column.sortValue?.(a) ?? '';
      const right = column.sortValue?.(b) ?? '';
      const result = typeof left === 'number' && typeof right === 'number'
        ? left - right
        : String(left).localeCompare(String(right), undefined, { numeric: true });
      return sortDirection === 'asc' ? result : -result;
    });
  }, [columns, rows, sortDirection, sortKey]);

  if (!rows.length) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr>{columns.map((column) => {
          const active = sortKey === column.key;
          const Icon = active ? sortDirection === 'asc' ? ChevronUp : ChevronDown : ChevronsUpDown;
          return (
            <th key={column.key} className={column.className}>
              {column.sortValue ? <button className="sort-button" onClick={() => {
                if (active) setSortDirection((value) => value === 'asc' ? 'desc' : 'asc');
                else { setSortKey(column.key); setSortDirection('asc'); }
              }}>{column.label}<Icon size={13} /></button> : column.label}
            </th>
          );
        })}</tr></thead>
        <tbody>{sorted.map((row) => (
          <tr key={rowKey(row)} onClick={() => onRowClick?.(row)} className={onRowClick ? 'row-clickable' : ''}>
            {columns.map((column) => <td key={column.key} className={column.className}>{column.render(row)}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
